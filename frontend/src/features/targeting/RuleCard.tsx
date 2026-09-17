import React from 'react';
import { TargetingRuleInput, Variation, ConditionGroupData } from '../../types';
import { ConditionGroup } from '../../components/conditions/ConditionGroup';
import { DistributionEditor } from './DistributionEditor';

interface RuleCardProps {
  rule: TargetingRuleInput;
  index: number;
  totalRules: number;
  variations: Variation[];
  onUpdate: (updated: TargetingRuleInput) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDelete: () => void;
  disabled?: boolean;
}

export const RuleCard: React.FC<RuleCardProps> = ({
  rule,
  index,
  totalRules,
  variations,
  onUpdate,
  onMoveUp,
  onMoveDown,
  onDelete,
  disabled = false,
}) => {
  // Ensure conditions object is normalized to ConditionGroupData
  const groupData: ConditionGroupData =
    rule.conditions && typeof rule.conditions === 'object' && 'operator' in rule.conditions
      ? (rule.conditions as ConditionGroupData)
      : { operator: 'AND', conditions: [] };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm space-y-4">
      {/* Header: Priority & Move buttons */}
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-xs font-bold text-indigo-400">
            #{rule.priority}
          </span>
          <span className="text-sm font-semibold text-[var(--text-primary)]">
            Quy tắc ưu tiên {rule.priority}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            title="Tăng độ ưu tiên (lên)"
            disabled={disabled || index === 0}
            onClick={onMoveUp}
            className="rounded border border-[var(--border)] bg-[var(--surface-sunken)] p-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:pointer-events-none"
            aria-label="Di chuyển lên"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
            </svg>
          </button>
          <button
            type="button"
            title="Giảm độ ưu tiên (xuống)"
            disabled={disabled || index === totalRules - 1}
            onClick={onMoveDown}
            className="rounded border border-[var(--border)] bg-[var(--surface-sunken)] p-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:pointer-events-none"
            aria-label="Di chuyển xuống"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <button
            type="button"
            title="Xóa rule này"
            disabled={disabled}
            onClick={onDelete}
            className="rounded border border-rose-500/30 bg-rose-500/10 p-1.5 text-xs text-rose-400 hover:bg-rose-500/20 disabled:opacity-40"
            aria-label="Xóa quy tắc"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      {/* Description */}
      <div>
        <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
          Mô tả quy tắc (tùy chọn)
        </label>
        <input
          type="text"
          value={rule.description || ''}
          placeholder="Ví dụ: Người dùng VIP tại Việt Nam"
          disabled={disabled}
          onChange={(e) => onUpdate({ ...rule, description: e.target.value })}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-tertiary)] focus:border-indigo-500 focus:outline-none"
        />
      </div>

      {/* Condition Group */}
      <div>
        <div className="mb-1 text-xs font-medium text-[var(--text-secondary)]">
          Điều kiện khớp (Context Match)
        </div>
        <ConditionGroup
          group={groupData}
          onChange={(newGroup) => onUpdate({ ...rule, conditions: newGroup })}
          disabled={disabled}
        />
      </div>

      {/* Distribution Rollout */}
      <DistributionEditor
        variations={variations}
        distribution={rule.distribution}
        onChange={(dist) => onUpdate({ ...rule, distribution: dist })}
        disabled={disabled}
      />
    </div>
  );
};
