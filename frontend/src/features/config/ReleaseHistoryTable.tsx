import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { configApi } from './api';
import { CompareReleasesModal } from './CompareReleasesModal';
import { History, RotateCcw, GitCompare, Calendar, AlertCircle } from 'lucide-react';
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
        'Rollback failed';
      setActionError(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
    },
  });

  const handleRollback = (version: number) => {
    if (
      window.confirm(
        `CONFIRM ROLLBACK: Are you sure you want to rollback to v${version}? This will generate a new release snapshot restoring this version's configuration.`
      )
    ) {
      rollbackMutation.mutate(version);
    }
  };

  if (isLoading) return <SkeletonTable rows={4} columns={4} />;
  if (isError) {
    return (
      <div className="rounded-md border border-status-danger/30 bg-status-danger/10 p-3 text-xs text-status-danger">
        Failed to load release history.
      </div>
    );
  }

  const sortedReleases = [...releases].sort((a, b) => b.version - a.version);

  return (
    <div className="space-y-3">
      {/* Action Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-brand" />
          <h3 className="text-xs font-semibold text-primary">
            Published Release History ({releases.length})
          </h3>
        </div>

        {sortedReleases.length >= 2 && (
          <button
            type="button"
            onClick={() => setIsCompareOpen(true)}
            className="flex items-center gap-1.5 rounded-xs border border-border-default bg-surface px-2.5 py-1 text-xs font-medium text-secondary hover:text-primary hover:bg-surface-elevated shadow-xs transition-colors"
          >
            <GitCompare className="w-3.5 h-3.5 text-brand" />
            <span>Compare Two Releases</span>
          </button>
        )}
      </div>

      {actionError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-xs border border-status-danger/30 bg-status-danger/10 p-2.5 text-xs text-status-danger font-mono"
        >
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {sortedReleases.length === 0 ? (
        <div className="rounded-md border border-dashed border-border-default p-10 text-center text-xs text-muted bg-surface/50">
          No configuration releases have been published for this namespace yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-border-default bg-surface shadow-xs">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-border-default bg-surface-elevated/40 text-secondary font-medium uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-2.5 px-3 font-semibold">Version</th>
                <th className="py-2.5 px-3 font-semibold">Changelog / Comment</th>
                <th className="py-2.5 px-3 font-semibold">Published At</th>
                <th className="py-2.5 px-3 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {sortedReleases.map((rel, idx) => (
                <tr key={rel.id} className="hover:bg-surface-elevated/50 transition-colors">
                  <td className="py-2.5 px-3 font-mono font-bold text-brand">
                    <span className="flex items-center gap-1.5">
                      v{rel.version}
                      {idx === 0 && (
                        <span className="rounded-xs bg-status-success/15 px-1.5 py-0.2 text-[10px] font-mono font-semibold text-status-success border border-status-success/30">
                          Active
                        </span>
                      )}
                      {rel.is_rollback_of && (
                        <span className="rounded-xs bg-status-warning/15 px-1.5 py-0.2 text-[10px] font-mono font-medium text-status-warning border border-status-warning/30">
                          Rollback of v{rel.is_rollback_of}
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-primary">
                    {rel.comment || <span className="text-muted italic">No comment provided</span>}
                  </td>
                  <td className="py-2.5 px-3 text-secondary">
                    <div className="flex items-center gap-1 font-mono text-[11px]">
                      <Calendar className="w-3 h-3 text-muted" />
                      <span>{new Date(rel.released_at).toLocaleString()}</span>
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    {idx !== 0 && (
                      <button
                        type="button"
                        disabled={rollbackMutation.isPending}
                        onClick={() => handleRollback(rel.version)}
                        className="inline-flex items-center gap-1 rounded-xs border border-status-warning/30 bg-status-warning/10 px-2 py-1 text-xs font-medium text-status-warning hover:bg-status-warning/20 transition-colors disabled:opacity-40"
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
