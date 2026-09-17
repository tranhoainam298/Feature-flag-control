"""Change Request Service — State Machine, Four-Eyes Approval, Impact Simulation, and Scheduled Changes."""

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FlagOpsError
from app.services import ruleset_cache
from app.engine.evaluator import evaluate
from app.engine.types import (
    DistributionEntry as EngineDistributionEntry,
    EvaluationContext,
    FlagRuleset as EngineFlagRuleset,
    Ruleset as EngineRuleset,
    TargetingRule as EngineTargetingRule,
    Variation as EngineVariation,
)
from app.models.change_request import ChangeRequest
from app.models.enums import ApiKeyScope, ChangeRequestStatus
from app.models.evaluation import EvaluationEvent
from app.models.flag import (
    Flag,
    FlagEnvironmentSetting,
    TargetingRule,
    Variation,
)
from app.models.project import Environment, Project
from app.models.user import User
from app.schemas.change_request import (
    ChangeRequestImpactResponse,
    ImpactTransition,
)
from app.services.eval import load_ruleset_bundle
from app.services.flag import bump_ruleset_version, create_audit_log

logger = logging.getLogger(__name__)


class ChangeRequestService:
    """Service handling change requests, state transitions, impact simulation, and execution."""

    async def list_change_requests(
        self,
        db: AsyncSession,
        env_id: UUID,
        status: ChangeRequestStatus | None = None,
    ) -> list[ChangeRequest]:
        """List change requests for an environment, optionally filtered by status."""
        query = select(ChangeRequest).where(ChangeRequest.environment_id == env_id)
        if status is not None:
            query = query.where(ChangeRequest.status == status)
        query = query.order_by(ChangeRequest.created_at.desc())
        result = await db.scalars(query)
        return list(result.all())

    async def get_change_request(
        self,
        db: AsyncSession,
        change_request_id: UUID,
    ) -> ChangeRequest:
        """Fetch change request by ID or raise 404."""
        cr = await db.scalar(select(ChangeRequest).where(ChangeRequest.id == change_request_id))
        if not cr:
            raise FlagOpsError(
                code="CHANGE_REQUEST_NOT_FOUND",
                message="Change request not found",
                status_code=404,
            )
        return cr

    async def create_change_request(
        self,
        db: AsyncSession,
        env_id: UUID,
        user_id: UUID,
        title: str,
        payload: dict[str, Any],
        description: str | None = None,
        scheduled_at: datetime | None = None,
        status: ChangeRequestStatus = ChangeRequestStatus.PENDING,
    ) -> ChangeRequest:
        """Create a new change request."""
        env = await db.scalar(select(Environment).where(Environment.id == env_id))
        if not env:
            raise FlagOpsError(
                code="ENVIRONMENT_NOT_FOUND",
                message="Environment not found",
                status_code=404,
            )

        cr = ChangeRequest(
            environment_id=env_id,
            title=title,
            description=description,
            payload=payload,
            status=status,
            requested_by=user_id,
            scheduled_at=scheduled_at,
        )
        db.add(cr)
        await db.flush()

        project = await db.scalar(select(Project).where(Project.id == env.project_id))
        await create_audit_log(
            db=db,
            actor_id=user_id,
            action="change_request.create",
            entity_type="change_request",
            entity_id=str(cr.id),
            organization_id=project.organization_id if project else None,
            project_id=env.project_id,
            environment_id=env_id,
            after={"status": cr.status.value, "title": cr.title},
        )
        await db.commit()
        await db.refresh(cr)
        return cr

    async def approve_change_request(
        self,
        db: AsyncSession,
        cr: ChangeRequest,
        reviewer_user: User,
    ) -> ChangeRequest:
        """Approve a change request adhering to the Four-Eyes principle.

        - If reviewer is the creator -> 403 SELF_APPROVAL_FORBIDDEN.
        - If scheduled in the future -> status = APPROVED.
        - If immediate (no schedule or scheduled_at <= now) -> applies payload atomically.
        """
        # 1. Four-eyes principle check
        if cr.requested_by == reviewer_user.id:
            raise FlagOpsError(
                code="SELF_APPROVAL_FORBIDDEN",
                message="Người tạo không được phép tự duyệt Change Request (nguyên tắc bốn mắt)",
                status_code=403,
            )

        # 2. State transition check
        if cr.status not in (ChangeRequestStatus.PENDING, ChangeRequestStatus.DRAFT):
            raise FlagOpsError(
                code="INVALID_STATE_TRANSITION",
                message=f"Change request in status '{cr.status.value}' cannot be approved",
                status_code=400,
            )

        cr.reviewed_by = reviewer_user.id
        now = datetime.now(timezone.utc)

        # 3. If scheduled for the future, set to APPROVED and wait for scheduler
        if cr.scheduled_at and cr.scheduled_at > now:
            cr.status = ChangeRequestStatus.APPROVED
            env = await db.scalar(select(Environment).where(Environment.id == cr.environment_id))
            project = (
                await db.scalar(select(Project).where(Project.id == env.project_id))
                if env
                else None
            )
            await create_audit_log(
                db=db,
                actor_id=reviewer_user.id,
                action="change_request.approved",
                entity_type="change_request",
                entity_id=str(cr.id),
                organization_id=project.organization_id if project else None,
                project_id=env.project_id if env else None,
                environment_id=cr.environment_id,
                after={"status": "APPROVED", "scheduled_at": cr.scheduled_at.isoformat()},
            )
            await db.commit()
            await db.refresh(cr)
            return cr

        # 4. Immediate execution: apply payload in 1 transaction
        await self.apply_payload(
            db=db,
            cr=cr,
            actor_id=reviewer_user.id,
            action_name="change_request.applied",
        )
        await db.commit()
        await db.refresh(cr)
        return cr

    async def reject_change_request(
        self,
        db: AsyncSession,
        cr: ChangeRequest,
        reviewer_user: User,
    ) -> ChangeRequest:
        """Reject a change request without applying changes."""
        if cr.status not in (ChangeRequestStatus.PENDING, ChangeRequestStatus.DRAFT):
            raise FlagOpsError(
                code="INVALID_STATE_TRANSITION",
                message=f"Change request in status '{cr.status.value}' cannot be rejected",
                status_code=400,
            )

        cr.reviewed_by = reviewer_user.id
        cr.status = ChangeRequestStatus.REJECTED

        env = await db.scalar(select(Environment).where(Environment.id == cr.environment_id))
        project = (
            await db.scalar(select(Project).where(Project.id == env.project_id)) if env else None
        )
        await create_audit_log(
            db=db,
            actor_id=reviewer_user.id,
            action="change_request.rejected",
            entity_type="change_request",
            entity_id=str(cr.id),
            organization_id=project.organization_id if project else None,
            project_id=env.project_id if env else None,
            environment_id=cr.environment_id,
            after={"status": "REJECTED"},
        )
        await db.commit()
        await db.refresh(cr)
        return cr

    async def cancel_change_request(
        self,
        db: AsyncSession,
        cr: ChangeRequest,
        user: User,
        is_admin: bool = False,
    ) -> ChangeRequest:
        """Cancel a change request (allowed by creator or admin)."""
        if cr.requested_by != user.id and not is_admin:
            raise FlagOpsError(
                code="FORBIDDEN",
                message="Only the requester or an administrator can cancel this change request",
                status_code=403,
            )

        if cr.status == ChangeRequestStatus.APPLIED:
            raise FlagOpsError(
                code="INVALID_STATE_TRANSITION",
                message="Cannot cancel a change request that has already been applied",
                status_code=400,
            )

        cr.status = ChangeRequestStatus.CANCELLED

        env = await db.scalar(select(Environment).where(Environment.id == cr.environment_id))
        project = (
            await db.scalar(select(Project).where(Project.id == env.project_id)) if env else None
        )
        await create_audit_log(
            db=db,
            actor_id=user.id,
            action="change_request.cancelled",
            entity_type="change_request",
            entity_id=str(cr.id),
            organization_id=project.organization_id if project else None,
            project_id=env.project_id if env else None,
            environment_id=cr.environment_id,
            after={"status": "CANCELLED"},
        )
        await db.commit()
        await db.refresh(cr)
        return cr

    async def apply_payload(
        self,
        db: AsyncSession,
        cr: ChangeRequest,
        actor_id: UUID | None,
        action_name: str,
    ) -> None:
        """Execute the change request payload atomically in ONE transaction.

        On failure, rolls back changes, ensures CR status remains APPROVED, and logs error.
        """
        try:
            # Execute database changes
            await self._execute_payload_mutations(db, cr)

            # Mark applied
            cr.status = ChangeRequestStatus.APPLIED
            cr.applied_at = datetime.now(timezone.utc)

            # Bump environment ruleset_version
            await bump_ruleset_version(db, cr.environment_id)

            # Invalidate Redis cache
            await ruleset_cache.invalidate(cr.environment_id)

            # Create audit log
            env = await db.scalar(select(Environment).where(Environment.id == cr.environment_id))
            project = (
                await db.scalar(select(Project).where(Project.id == env.project_id))
                if env
                else None
            )
            await create_audit_log(
                db=db,
                actor_id=actor_id,
                action=action_name,
                entity_type="change_request",
                entity_id=str(cr.id),
                organization_id=project.organization_id if project else None,
                project_id=env.project_id if env else None,
                environment_id=cr.environment_id,
                after={"status": "APPLIED", "applied_at": cr.applied_at.isoformat()},
            )
        except Exception as exc:
            logger.error(
                "Error applying change request payload for CR %s: %s",
                cr.id,
                exc,
                exc_info=True,
            )
            await db.rollback()

            # Ensure CR status is APPROVED in DB so it can be retried or inspected
            cr.status = ChangeRequestStatus.APPROVED
            db.add(cr)
            await db.commit()

            raise FlagOpsError(
                code="PAYLOAD_APPLICATION_FAILED",
                message=f"Failed to apply change request payload: {str(exc)}",
                status_code=500,
            ) from exc

    async def _execute_payload_mutations(self, db: AsyncSession, cr: ChangeRequest) -> None:
        """Internal helper to mutate settings or targeting rules according to payload."""
        payload = cr.payload
        action_type = payload.get("type") or payload.get("action")

        # Support flag_setting updates
        if action_type == "flag_setting" or "setting" in payload:
            flag_id = UUID(str(payload["flag_id"]))
            setting = await db.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_id,
                    FlagEnvironmentSetting.environment_id == cr.environment_id,
                )
            )
            if not setting:
                raise ValueError(f"FlagEnvironmentSetting not found for flag {flag_id}")

            setting_data = payload.get("setting") or payload.get("changes") or {}
            if "enabled" in setting_data and setting_data["enabled"] is not None:
                setting.enabled = setting_data["enabled"]
            if "default_variation_id" in setting_data and setting_data["default_variation_id"]:
                setting.default_variation_id = UUID(str(setting_data["default_variation_id"]))
            if "off_variation_id" in setting_data and setting_data["off_variation_id"]:
                setting.off_variation_id = UUID(str(setting_data["off_variation_id"]))
            if "bucketing_key" in setting_data and setting_data["bucketing_key"]:
                setting.bucketing_key = setting_data["bucketing_key"]

        # Support targeting rules updates
        elif action_type == "targeting_rules" or "rules" in payload:
            flag_id = UUID(str(payload["flag_id"]))
            setting = await db.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_id,
                    FlagEnvironmentSetting.environment_id == cr.environment_id,
                )
            )
            if not setting:
                raise ValueError(f"FlagEnvironmentSetting not found for flag {flag_id}")

            # Delete old rules
            await db.execute(
                delete(TargetingRule).where(
                    TargetingRule.flag_environment_setting_id == setting.id
                )
            )

            # Insert new rules
            new_rules = payload.get("rules", [])
            for r_data in new_rules:
                rule = TargetingRule(
                    flag_environment_setting_id=setting.id,
                    priority=r_data["priority"],
                    description=r_data.get("description"),
                    conditions=r_data.get("conditions", {}),
                    distribution=r_data.get("distribution", []),
                    segment_id=UUID(str(r_data["segment_id"]))
                    if r_data.get("segment_id")
                    else None,
                )
                db.add(rule)

    async def simulate_impact(
        self,
        db: AsyncSession,
        cr: ChangeRequest,
    ) -> ChangeRequestImpactResponse:
        """Simulate the impact of proposed changes on historical contexts without modifying the DB.

        Pulls up to 1,000 most recent evaluation events for the environment and runs the
        pure evaluation engine twice: once with the current ruleset and once with the
        simulated in-memory ruleset.
        """
        env = await db.scalar(select(Environment).where(Environment.id == cr.environment_id))
        if not env:
            raise FlagOpsError(
                code="ENVIRONMENT_NOT_FOUND",
                message="Environment not found",
                status_code=404,
            )

        # 1. Load current ruleset
        current_ruleset, _, flags_map = await load_ruleset_bundle(
            db, env, scope=ApiKeyScope.SERVER
        )

        # 2. Identify the target flag
        target_flag_key: str | None = cr.payload.get("flag_key")
        flag_id_str = cr.payload.get("flag_id")

        target_flag: Flag | None = None
        if flag_id_str:
            target_flag = await db.scalar(select(Flag).where(Flag.id == UUID(str(flag_id_str))))
            if target_flag:
                target_flag_key = target_flag.key

        if not target_flag_key or target_flag_key not in current_ruleset.flags:
            # If no flag or flag not found in ruleset, return 0 impact
            return ChangeRequestImpactResponse(
                total_contexts=0,
                affected_contexts=0,
                change_percentage=0.0,
                transitions=[],
                summary="Không tìm thấy flag tương ứng để mô phỏng tác động.",
                flag_key=target_flag_key,
            )

        # 3. Construct simulated in-memory ruleset
        cur_flag_ruleset = current_ruleset.flags[target_flag_key]
        simulated_flag_ruleset = self._build_simulated_flag_ruleset(
            cur_flag_ruleset=cur_flag_ruleset,
            payload=cr.payload,
        )

        simulated_ruleset = EngineRuleset(
            environment_id=current_ruleset.environment_id,
            ruleset_version=current_ruleset.ruleset_version + 1,
            flags={**current_ruleset.flags, target_flag_key: simulated_flag_ruleset},
            segments=current_ruleset.segments,
        )

        # 4. Fetch up to 1000 recent evaluation events
        evt_query = (
            select(EvaluationEvent)
            .where(EvaluationEvent.environment_id == env.id)
            .order_by(EvaluationEvent.created_at.desc())
            .limit(1000)
        )
        if target_flag:
            evt_query = evt_query.where(EvaluationEvent.flag_id == target_flag.id)

        events = list((await db.scalars(evt_query)).all())
        total_contexts = len(events)

        if total_contexts == 0:
            return ChangeRequestImpactResponse(
                total_contexts=0,
                affected_contexts=0,
                change_percentage=0.0,
                transitions=[],
                summary="Chưa có dữ liệu evaluation event của environment này để mô phỏng tác động.",
                flag_key=target_flag_key,
            )

        # 5. Run evaluation engine twice for each context
        affected_count = 0
        transition_counter: Counter[tuple[str, str]] = Counter()

        for evt in events:
            # Build context from stored context dict or context_key_hash
            if evt.context and isinstance(evt.context, dict):
                t_key = (
                    evt.context.get("targetingKey")
                    or evt.context.get("targeting_key")
                    or evt.context_key_hash
                )
                attrs = evt.context.get("attributes") or {
                    k: v
                    for k, v in evt.context.items()
                    if k not in ("targetingKey", "targeting_key")
                }
            else:
                t_key = evt.context_key_hash
                attrs = {}

            ctx = EvaluationContext(targeting_key=str(t_key), attributes=attrs)

            res_current = evaluate(current_ruleset, ctx, target_flag_key)
            res_simulated = evaluate(simulated_ruleset, ctx, target_flag_key)

            var_cur = res_current.variant or "none"
            var_sim = res_simulated.variant or "none"

            if var_cur != var_sim:
                affected_count += 1
                transition_counter[(var_cur, var_sim)] += 1

        change_pct = (
            round((affected_count / total_contexts) * 100.0, 2) if total_contexts > 0 else 0.0
        )
        transitions = [
            ImpactTransition(from_variation=pair[0], to_variation=pair[1], count=cnt)
            for pair, cnt in transition_counter.items()
        ]

        if affected_count == 0:
            summary = f"Thay đổi này không làm thay đổi kết quả đánh giá cho {total_contexts} context được khảo sát."
        else:
            summary = (
                f"Thay đổi này ảnh hưởng {change_pct}% người dùng: "
                f"{affected_count}/{total_contexts} chuyển đổi variation."
            )

        return ChangeRequestImpactResponse(
            total_contexts=total_contexts,
            affected_contexts=affected_count,
            change_percentage=change_pct,
            transitions=transitions,
            summary=summary,
            flag_key=target_flag_key,
        )

    def _build_simulated_flag_ruleset(
        self,
        cur_flag_ruleset: EngineFlagRuleset,
        payload: dict[str, Any],
    ) -> EngineFlagRuleset:
        """Create a modified copy of EngineFlagRuleset purely in-memory."""
        action_type = payload.get("type") or payload.get("action")
        var_by_id = {v.id: v for v in cur_flag_ruleset.variations if v.id}
        var_by_key = {v.key: v for v in cur_flag_ruleset.variations}

        new_enabled = cur_flag_ruleset.enabled
        new_bucketing_key = cur_flag_ruleset.bucketing_key
        new_default_var = cur_flag_ruleset.default_variation
        new_off_var = cur_flag_ruleset.off_variation
        new_rules = list(cur_flag_ruleset.rules)

        if action_type == "flag_setting" or "setting" in payload:
            settings_data = payload.get("setting") or payload.get("changes") or {}
            if "enabled" in settings_data and settings_data["enabled"] is not None:
                new_enabled = bool(settings_data["enabled"])
            if "bucketing_key" in settings_data and settings_data["bucketing_key"]:
                new_bucketing_key = str(settings_data["bucketing_key"])
            if "default_variation_id" in settings_data and settings_data["default_variation_id"]:
                d_id = str(settings_data["default_variation_id"])
                new_default_var = var_by_id.get(d_id, var_by_key.get(d_id, new_default_var))
            if "off_variation_id" in settings_data and settings_data["off_variation_id"]:
                o_id = str(settings_data["off_variation_id"])
                new_off_var = var_by_id.get(o_id, var_by_key.get(o_id, new_off_var))

        elif action_type == "targeting_rules" or "rules" in payload:
            raw_rules = payload.get("rules", [])
            new_rules = []
            for r in raw_rules:
                # Build engine distribution
                dist_entries: list[EngineDistributionEntry] = []
                for d in r.get("distribution", []):
                    var_id = str(d.get("variation_id"))
                    target_var = var_by_id.get(var_id, var_by_key.get(var_id))
                    if target_var:
                        dist_entries.append(
                            EngineDistributionEntry(
                                variation=target_var,
                                weight=float(d.get("weight", 0.0)),
                            )
                        )

                new_rules.append(
                    EngineTargetingRule(
                        id=str(r.get("id", "sim-rule")),
                        priority=int(r.get("priority", 1)),
                        description=r.get("description"),
                        conditions=r.get("conditions", {}),
                        distribution=dist_entries,
                        segment_id=str(r.get("segment_id")) if r.get("segment_id") else None,
                    )
                )

        return EngineFlagRuleset(
            flag_id=cur_flag_ruleset.flag_id,
            flag_key=cur_flag_ruleset.flag_key,
            flag_type=cur_flag_ruleset.flag_type,
            enabled=new_enabled,
            bucketing_key=new_bucketing_key,
            default_variation=new_default_var,
            off_variation=new_off_var,
            variations=cur_flag_ruleset.variations,
            rules=new_rules,
            overrides=cur_flag_ruleset.overrides,
        )

    async def process_scheduled_change_requests(self, db: AsyncSession) -> int:
        """Scan and atomically apply all APPROVED change requests that have reached scheduled_at.

        Audit log records actor_id = None and action = 'change_request.applied_by_scheduler'.
        """
        now = datetime.now(timezone.utc)
        query = (
            select(ChangeRequest)
            .where(
                ChangeRequest.status == ChangeRequestStatus.APPROVED,
                ChangeRequest.scheduled_at <= now,
            )
            .order_by(ChangeRequest.scheduled_at.asc())
        )
        crs = list((await db.scalars(query)).all())
        applied_count = 0

        for cr in crs:
            try:
                await self.apply_payload(
                    db=db,
                    cr=cr,
                    actor_id=None,
                    action_name="change_request.applied_by_scheduler",
                )
                await db.commit()
                applied_count += 1
                logger.info(
                    "Applied scheduled change request %s (scheduled for %s)",
                    cr.id,
                    cr.scheduled_at,
                )
            except Exception as exc:
                logger.error(
                    "Scheduler failed to apply change request %s: %s",
                    cr.id,
                    exc,
                    exc_info=True,
                )

        return applied_count


change_request_service = ChangeRequestService()
