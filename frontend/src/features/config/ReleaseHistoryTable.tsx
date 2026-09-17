import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { configApi } from './api';
import { CompareReleasesModal } from './CompareReleasesModal';
import { History, RotateCcw, GitCompare, Calendar } from 'lucide-react';
import { SkeletonTable } from '../../components/ui/SkeletonTable';

interface ReleaseHistoryTableProps {
  namespaceId: string;
}

export const ReleaseHistoryTable: React.FC<ReleaseHistoryTableProps> = ({
  namespaceId,
}) => {
  const queryClient = useQueryClient();
  const [isCompareOpen, setIsCompareOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: releases = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['config-releases', namespaceId],
    queryFn: () => configApi.listReleases(namespaceId),
    enabled: !!namespaceId,
  });

  const rollbackMutation = useMutation({
    mutationFn: (version: number) => configApi.rollbackRelease(namespaceId, version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-releases', namespaceId] });
      queryClient.invalidateQueries({ queryKey: ['config-draft-items', namespaceId] });
      queryClient.invalidateQueries({ queryKey: ['config-pending-diff', namespaceId] });
      setActionError(null);
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Rollback thất bại';
      setActionError(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
    },
  });

  const handleRollback = (version: number) => {
    if (
      window.confirm(
        `XÁC NHẬN ROLLBACK: Bạn có chắc chắn muốn rollback cấu hình về phiên bản v${version} không? Thao tác này sẽ tạo một release mới ghi đè cấu hình hiện tại.`
      )
    ) {
      rollbackMutation.mutate(version);
    }
  };

  if (isLoading) return <SkeletonTable rows={4} columns={4} />;
  if (isError) {
    return (
      <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-400">
        Lỗi tải lịch sử release.
      </div>
    );
  }

  const sortedReleases = [...releases].sort((a, b) => b.version - a.version);

  return (
    <div className="space-y-4">
      {/* Action Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Lịch sử các phiên bản phát hành ({releases.length})
          </h3>
        </div>

        {sortedReleases.length >= 2 && (
          <button
            type="button"
            onClick={() => setIsCompareOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-hover)] shadow-sm"
          >
            <GitCompare className="w-3.5 h-3.5 text-indigo-400" />
            <span>So sánh 2 phiên bản</span>
          </button>
        )}
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-400 font-mono"
        >
          {actionError}
        </div>
      )}

      {sortedReleases.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-10 text-center text-xs text-[var(--text-tertiary)]">
          Chưa có phiên bản release nào được phát hành cho namespace này.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-sm">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[var(--border)] bg-[var(--surface-sunken)] text-[var(--text-secondary)]">
              <tr>
                <th className="py-3 px-4 font-semibold">Phiên bản</th>
                <th className="py-3 px-4 font-semibold">Ghi chú (Comment)</th>
                <th className="py-3 px-4 font-semibold">Thời điểm phát hành</th>
                <th className="py-3 px-4 font-semibold text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {sortedReleases.map((rel, idx) => (
                <tr key={rel.id} className="hover:bg-[var(--surface-hover)] transition-colors">
                  <td className="py-3 px-4 font-mono font-bold text-indigo-400">
                    <span className="flex items-center gap-1.5">
                      v{rel.version}
                      {idx === 0 && (
                        <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-sans font-semibold text-emerald-300">
                          Hiện tại
                        </span>
                      )}
                      {rel.is_rollback_of && (
                        <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-sans font-medium text-amber-300">
                          Rollback
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-[var(--text-primary)]">
                    {rel.comment || <span className="text-[var(--text-tertiary)] italic">Không có</span>}
                  </td>
                  <td className="py-3 px-4 text-[var(--text-secondary)]">
                    <div className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-[var(--text-tertiary)]" />
                      <span>{new Date(rel.released_at).toLocaleString()}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right">
                    {idx !== 0 && (
                      <button
                        type="button"
                        disabled={rollbackMutation.isPending}
                        onClick={() => handleRollback(rel.version)}
                        className="inline-flex items-center gap-1 rounded border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-400 hover:bg-amber-500/20 transition-colors disabled:opacity-40"
                      >
                        <RotateCcw className="w-3 h-3" />
                        <span>Rollback</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Compare Modal */}
      {isCompareOpen && (
        <CompareReleasesModal
          namespaceId={namespaceId}
          releases={sortedReleases}
          isOpen={isCompareOpen}
          onClose={() => setIsCompareOpen(false)}
        />
      )}
    </div>
  );
};
