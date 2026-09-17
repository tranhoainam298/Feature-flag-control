import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChangeRequest, ChangeRequestImpact } from '../../types';
import { changeRequestApi } from './api';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import {
  ShieldAlert,
  Clock,
  User,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  PlayCircle,
  Loader2,
  GitCompare,
  Check,
  Ban,
  Calendar,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';

interface Props {
  changeRequest: ChangeRequest | null;
  isOpen: boolean;
  onClose: () => void;
}

export const ChangeRequestDetailModal: React.FC<Props> = ({
  changeRequest,
  isOpen,
  onClose,
}) => {
  const { user } = useApp();
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);

  // Impact Simulation Query
  const {
    data: impact,
    isLoading: isLoadingImpact,
    refetch: runImpactSimulation,
    isFetching: isFetchingImpact,
  } = useQuery<ChangeRequestImpact>({
    queryKey: ['change-request-impact', changeRequest?.id],
    queryFn: () => changeRequestApi.getImpact(changeRequest!.id),
    enabled: isOpen && !!changeRequest,
    staleTime: 60 * 1000,
  });

  const approveMutation = useMutation({
    mutationFn: () => changeRequestApi.approve(changeRequest!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['change-requests'] });
      queryClient.invalidateQueries({ queryKey: ['flags'] });
      onClose();
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Failed to approve Change Request.';
      setActionError(msg);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => changeRequestApi.reject(changeRequest!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['change-requests'] });
      onClose();
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Failed to reject Change Request.';
      setActionError(msg);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => changeRequestApi.cancel(changeRequest!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['change-requests'] });
      onClose();
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Failed to cancel Change Request.';
      setActionError(msg);
    },
  });

  if (!changeRequest) return null;

  const isCreator = user?.id === changeRequest.requested_by;
  const isPending = changeRequest.status === 'PENDING' || changeRequest.status === 'DRAFT';
  const isApproved = changeRequest.status === 'APPROVED';
  const isApplied = changeRequest.status === 'APPLIED';
  const isRejected = changeRequest.status === 'REJECTED';

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPLIED':
        return <Badge variant="success">APPLIED</Badge>;
      case 'APPROVED':
        return <Badge variant="default">APPROVED</Badge>;
      case 'PENDING':
        return <Badge variant="warning">PENDING</Badge>;
      case 'REJECTED':
        return <Badge variant="danger">REJECTED</Badge>;
      case 'CANCELLED':
        return <Badge variant="outline">CANCELLED</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={changeRequest.title}
      description={`CR ID: ${changeRequest.id}`}
      maxWidth="xl"
    >
      <div className="space-y-4 text-xs pb-2">
        {/* Error Notification */}
        {actionError && (
          <div className="p-2.5 bg-status-danger/10 border border-status-danger/20 text-status-danger rounded-xs text-xs flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Four-Eyes Principle Warning */}
        {isCreator && isPending && (
          <div className="p-3 bg-status-warning/10 border border-status-warning/20 text-status-warning rounded-xs text-xs flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block">Four-Eyes Principle Enforced</span>
              <span>
                You created this Change Request. Production policies strictly require an independent review. Another administrator (ADMIN or OWNER) must approve this change.
              </span>
            </div>
          </div>
        )}

        {/* Header Metadata Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <div className="p-2.5 rounded-xs bg-surface-elevated/40 border border-border-default">
            <span className="text-[10px] text-muted uppercase tracking-wider block mb-1">Status</span>
            <div>{getStatusBadge(changeRequest.status)}</div>
          </div>

          <div className="p-2.5 rounded-xs bg-surface-elevated/40 border border-border-default">
            <span className="text-[10px] text-muted uppercase tracking-wider block mb-1">Requester</span>
            <div className="flex items-center gap-1.5 text-xs text-primary font-mono truncate">
              <User className="w-3.5 h-3.5 text-muted shrink-0" />
              <span className="truncate">{changeRequest.requested_by.slice(0, 8)}...</span>
              {isCreator && <span className="text-[10px] text-brand font-sans">(You)</span>}
            </div>
          </div>

          <div className="p-2.5 rounded-xs bg-surface-elevated/40 border border-border-default">
            <span className="text-[10px] text-muted uppercase tracking-wider block mb-1">Created At</span>
            <div className="flex items-center gap-1.5 text-xs text-secondary font-mono truncate">
              <Clock className="w-3.5 h-3.5 text-muted shrink-0" />
              <span>{new Date(changeRequest.created_at).toLocaleDateString()}</span>
            </div>
          </div>

          <div className="p-2.5 rounded-xs bg-surface-elevated/40 border border-border-default">
            <span className="text-[10px] text-muted uppercase tracking-wider block mb-1">Scheduled For</span>
            <div className="flex items-center gap-1.5 text-xs text-secondary font-mono truncate">
              <Calendar className="w-3.5 h-3.5 text-muted shrink-0" />
              <span>
                {changeRequest.scheduled_at
                  ? new Date(changeRequest.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : 'Immediate'}
              </span>
            </div>
          </div>
        </div>

        {/* Description if present */}
        {changeRequest.description && (
          <div className="p-2.5 bg-surface-elevated/40 border border-border-default rounded-xs text-xs text-secondary">
            <span className="font-semibold text-primary block mb-0.5">Business Justification:</span>
            {changeRequest.description}
          </div>
        )}

        {/* Impact Simulation Section — Pure Evaluation Engine Highlight */}
        <div className="p-3.5 rounded-md bg-surface border border-brand/20 shadow-xs relative overflow-hidden space-y-3">
          <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-xs bg-brand/10 flex items-center justify-center text-brand border border-brand/20">
                <GitCompare className="w-3.5 h-3.5" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-primary">
                  In-Memory Impact Simulation
                </h3>
                <span className="text-[10px] text-muted">
                  Pure evaluation engine executed over historical live context events without database writes
                </span>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => runImpactSimulation()}
              disabled={isFetchingImpact}
              className="gap-1.5 text-xs h-7 px-2"
            >
              {isFetchingImpact ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <PlayCircle className="w-3 h-3 text-brand" />
              )}
              <span>Rerun Simulation</span>
            </Button>
          </div>

          {isLoadingImpact || isFetchingImpact ? (
            <div className="py-5 flex flex-col items-center justify-center text-secondary gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-brand" />
              <span className="text-xs font-mono">
                Executing pure engine evaluation on recent contexts...
              </span>
            </div>
          ) : impact ? (
            <div className="space-y-2.5">
              {/* Summary message */}
              <div
                className={`p-2.5 rounded-xs border text-xs ${
                  impact.affected_contexts > 0
                    ? 'bg-status-warning/10 border-status-warning/20 text-status-warning'
                    : 'bg-status-success/10 border-status-success/20 text-status-success'
                }`}
              >
                <div className="flex items-center gap-2 font-medium">
                  {impact.affected_contexts > 0 ? (
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                  )}
                  <span>{impact.summary}</span>
                </div>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-3 gap-2.5">
                <div className="p-2 bg-surface-elevated/40 rounded-xs border border-border-default text-center">
                  <span className="text-[10px] text-muted uppercase tracking-wider block">Sampled Contexts</span>
                  <span className="text-sm font-bold text-primary font-mono">
                    {impact.total_contexts.toLocaleString()}
                  </span>
                </div>
                <div className="p-2 bg-surface-elevated/40 rounded-xs border border-border-default text-center">
                  <span className="text-[10px] text-muted uppercase tracking-wider block">Altered Outcomes</span>
                  <span className="text-sm font-bold text-status-warning font-mono">
                    {impact.affected_contexts.toLocaleString()}
                  </span>
                </div>
                <div className="p-2 bg-surface-elevated/40 rounded-xs border border-border-default text-center">
                  <span className="text-[10px] text-muted uppercase tracking-wider block">Impact Percentage</span>
                  <span className="text-sm font-bold text-brand font-mono">
                    {impact.change_percentage}%
                  </span>
                </div>
              </div>

              {/* Transitions breakdown */}
              {impact.transitions.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  <span className="text-[10px] font-semibold text-secondary uppercase tracking-wider block">
                    Variation Transition Matrix:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {impact.transitions.map((t, idx) => (
                      <div
                        key={idx}
                        className="p-1.5 bg-surface-elevated border border-border-default rounded-xs flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-1.5 font-mono">
                          <span className="px-1.5 py-0.2 rounded-xs bg-surface text-muted text-[11px] border border-border-subtle">
                            {t.from_variation}
                          </span>
                          <span className="text-muted text-[11px]">→</span>
                          <span className="px-1.5 py-0.2 rounded-xs bg-brand/10 text-brand font-semibold text-[11px] border border-brand/20">
                            {t.to_variation}
                          </span>
                        </div>
                        <span className="font-mono text-xs font-semibold text-primary">
                          {t.count} {t.count === 1 ? 'context' : 'contexts'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Payload Diff Section */}
        <div>
          <span className="text-[10px] font-semibold text-secondary uppercase tracking-wider block mb-1.5">
            Proposed Mutation (Payload Diff)
          </span>
          <div className="bg-canvas border border-border-default rounded-xs p-2.5 font-mono text-xs text-status-success overflow-x-auto max-h-48">
            <pre>{JSON.stringify(changeRequest.payload, null, 2)}</pre>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-border-subtle">
          <div>
            {!isApplied && !isRejected && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="gap-1.5 text-muted hover:text-status-danger hover:border-status-danger/30 text-xs h-7 px-2.5"
              >
                <Ban className="w-3.5 h-3.5" />
                <span>Cancel Request</span>
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {isPending && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => rejectMutation.mutate()}
                  disabled={rejectMutation.isPending}
                  className="gap-1.5 text-status-danger hover:bg-status-danger/10 border-status-danger/20 text-xs h-7 px-2.5"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  <span>Reject</span>
                </Button>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => approveMutation.mutate()}
                  disabled={isCreator || approveMutation.isPending}
                  title={
                    isCreator
                      ? 'Four-Eyes Principle: Requester cannot self-approve'
                      : 'Approve Change Request'
                  }
                  className="gap-1.5 text-xs h-7 px-3"
                >
                  {approveMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Check className="w-3.5 h-3.5" />
                  )}
                  <span>Approve & Apply</span>
                </Button>
              </>
            )}

            {isApproved && (
              <span className="text-xs text-muted font-mono italic">
                Approved — Awaiting background scheduler window...
              </span>
            )}

            {isApplied && (
              <span className="text-xs text-status-success font-mono flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Changes successfully applied to production</span>
              </span>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
};
