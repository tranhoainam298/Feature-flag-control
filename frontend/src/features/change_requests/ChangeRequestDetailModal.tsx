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
        'Không thể duyệt Change Request.';
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
        'Không thể từ chối Change Request.';
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
        'Không thể hủy Change Request.';
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
      <div className="space-y-6 text-sm pb-2">
        {/* Error Notification */}
        {actionError && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-md text-xs flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Four-Eyes Principle Warning */}
        {isCreator && isPending && (
          <div className="p-3.5 bg-amber-500/10 border border-amber-500/20 text-amber-300 rounded-md text-xs flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block">Nguyên tắc bốn mắt (Four-Eyes Principle)</span>
              <span>
                Bạn là người tạo Change Request này. Để đảm bảo an toàn cho môi trường Production, bạn không được phép tự duyệt. Yêu cầu một Quản trị viên (ADMIN/OWNER) khác phê duyệt.
              </span>
            </div>
          </div>
        )}

        {/* Header Metadata Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-md bg-canvas border border-border-subtle">
            <span className="text-[11px] text-muted block mb-1">Trạng thái</span>
            <div>{getStatusBadge(changeRequest.status)}</div>
          </div>

          <div className="p-3 rounded-md bg-canvas border border-border-subtle">
            <span className="text-[11px] text-muted block mb-1">Người yêu cầu</span>
            <div className="flex items-center gap-1.5 text-xs text-primary font-mono truncate">
              <User className="w-3.5 h-3.5 text-muted shrink-0" />
              <span className="truncate">{changeRequest.requested_by.slice(0, 8)}...</span>
              {isCreator && <span className="text-[10px] text-brand">(Bạn)</span>}
            </div>
          </div>

          <div className="p-3 rounded-md bg-canvas border border-border-subtle">
            <span className="text-[11px] text-muted block mb-1">Ngày tạo</span>
            <div className="flex items-center gap-1.5 text-xs text-secondary font-mono truncate">
              <Clock className="w-3.5 h-3.5 text-muted shrink-0" />
              <span>{new Date(changeRequest.created_at).toLocaleDateString()}</span>
            </div>
          </div>

          <div className="p-3 rounded-md bg-canvas border border-border-subtle">
            <span className="text-[11px] text-muted block mb-1">Hẹn giờ (Scheduled)</span>
            <div className="flex items-center gap-1.5 text-xs text-secondary font-mono truncate">
              <Calendar className="w-3.5 h-3.5 text-muted shrink-0" />
              <span>
                {changeRequest.scheduled_at
                  ? new Date(changeRequest.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : 'Ngay tức thì'}
              </span>
            </div>
          </div>
        </div>

        {/* Description if present */}
        {changeRequest.description && (
          <div className="p-3 bg-surface border border-border-subtle rounded-md text-xs text-secondary">
            <span className="font-semibold text-primary block mb-1">Mô tả lý do:</span>
            {changeRequest.description}
          </div>
        )}

        {/* Impact Simulation Section — Pure Evaluation Engine Highlight */}
        <div className="p-4 rounded-lg bg-surface border border-brand/20 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between mb-3 border-b border-border-subtle pb-2.5">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-brand/10 flex items-center justify-center text-brand">
                <GitCompare className="w-3.5 h-3.5" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-primary">
                  Mô phỏng tác động (Impact Simulation)
                </h3>
                <span className="text-[10px] text-muted">
                  Đánh giá pure engine trên dữ liệu context thực tế mà không cần ghi DB
                </span>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => runImpactSimulation()}
              disabled={isFetchingImpact}
              className="gap-1.5 text-xs"
            >
              {isFetchingImpact ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <PlayCircle className="w-3 h-3 text-brand" />
              )}
              <span>Chạy lại mô phỏng</span>
            </Button>
          </div>

          {isLoadingImpact || isFetchingImpact ? (
            <div className="py-6 flex flex-col items-center justify-center text-secondary gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-brand" />
              <span className="text-xs font-mono">
                Đang chạy pure evaluation engine trên 1,000 context gần nhất...
              </span>
            </div>
          ) : impact ? (
            <div className="space-y-3">
              {/* Summary message */}
              <div
                className={`p-3 rounded-md border text-xs ${
                  impact.affected_contexts > 0
                    ? 'bg-amber-500/10 border-amber-500/20 text-amber-300'
                    : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                }`}
              >
                <div className="flex items-center gap-2 font-medium">
                  {impact.affected_contexts > 0 ? (
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  )}
                  <span>{impact.summary}</span>
                </div>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-2.5 bg-canvas rounded border border-border-subtle text-center">
                  <span className="text-[11px] text-muted block">Tổng context khảo sát</span>
                  <span className="text-base font-bold text-primary font-mono">
                    {impact.total_contexts.toLocaleString()}
                  </span>
                </div>
                <div className="p-2.5 bg-canvas rounded border border-border-subtle text-center">
                  <span className="text-[11px] text-muted block">Số lượng đổi kết quả</span>
                  <span className="text-base font-bold text-amber-400 font-mono">
                    {impact.affected_contexts.toLocaleString()}
                  </span>
                </div>
                <div className="p-2.5 bg-canvas rounded border border-border-subtle text-center">
                  <span className="text-[11px] text-muted block">Tỉ lệ ảnh hưởng</span>
                  <span className="text-base font-bold text-brand font-mono">
                    {impact.change_percentage}%
                  </span>
                </div>
              </div>

              {/* Transitions breakdown */}
              {impact.transitions.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  <span className="text-[11px] font-semibold text-secondary uppercase tracking-wider block">
                    Bảng chuyển dịch Variation:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {impact.transitions.map((t, idx) => (
                      <div
                        key={idx}
                        className="p-2 bg-canvas/80 border border-border-subtle rounded flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2 font-mono">
                          <span className="px-1.5 py-0.5 rounded bg-surface text-muted">
                            {t.from_variation}
                          </span>
                          <span className="text-muted">→</span>
                          <span className="px-1.5 py-0.5 rounded bg-brand/10 text-brand font-semibold">
                            {t.to_variation}
                          </span>
                        </div>
                        <span className="font-mono text-xs font-semibold text-primary">
                          {t.count} users
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
          <span className="text-xs font-semibold text-secondary uppercase tracking-wider block mb-2">
            Tập thay đổi (Payload Diff)
          </span>
          <div className="bg-[#0f141c] border border-border-subtle rounded-md p-3 font-mono text-xs text-emerald-400 overflow-x-auto max-h-48">
            <pre>{JSON.stringify(changeRequest.payload, null, 2)}</pre>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-between pt-4 border-t border-border-subtle">
          <div>
            {!isApplied && !isRejected && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="gap-1.5 text-muted hover:text-rose-400 hover:border-rose-500/30"
              >
                <Ban className="w-3.5 h-3.5" />
                <span>Hủy yêu cầu</span>
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
                  className="gap-1.5 text-rose-400 hover:bg-rose-500/10 border-rose-500/20"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  <span>Từ chối (Reject)</span>
                </Button>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => approveMutation.mutate()}
                  disabled={isCreator || approveMutation.isPending}
                  title={
                    isCreator
                      ? 'Nguyên tắc bốn mắt: Người tạo không thể tự duyệt'
                      : 'Duyệt Change Request'
                  }
                  className="gap-1.5"
                >
                  {approveMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Check className="w-3.5 h-3.5" />
                  )}
                  <span>Duyệt & Áp dụng</span>
                </Button>
              </>
            )}

            {isApproved && (
              <span className="text-xs text-muted font-mono italic">
                Đã duyệt — Đang chờ APScheduler đến giờ áp dụng...
              </span>
            )}

            {isApplied && (
              <span className="text-xs text-emerald-400 font-mono flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Thay đổi đã áp dụng vào production</span>
              </span>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
};
