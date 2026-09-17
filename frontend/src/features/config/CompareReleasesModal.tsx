import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { configApi } from './api';
import { ConfigRelease } from '../../types';
import { ConfigDiffModal } from './ConfigDiffModal';
import { GitCompare, X } from 'lucide-react';

interface CompareReleasesModalProps {
  namespaceId: string;
  releases: ConfigRelease[];
  isOpen: boolean;
  onClose: () => void;
}

export const CompareReleasesModal: React.FC<CompareReleasesModalProps> = ({
  namespaceId,
  releases,
  isOpen,
  onClose,
}) => {
  const sorted = [...releases].sort((a, b) => b.version - a.version);
  const [v1, setV1] = useState<number>(() => sorted[1]?.version ?? sorted[0]?.version ?? 1);
  const [v2, setV2] = useState<number>(() => sorted[0]?.version ?? 1);
  const [showDiff, setShowDiff] = useState(false);

  const { data: diff, isLoading, isError } = useQuery({
    queryKey: ['releases-diff', namespaceId, v1, v2],
    queryFn: () => configApi.getReleasesDiff(namespaceId, v1, v2),
    enabled: isOpen && showDiff && v1 !== undefined && v2 !== undefined,
  });

  if (!isOpen) return null;

  if (showDiff && diff) {
    return (
      <ConfigDiffModal
        title={`Comparing Releases v${v1} → v${v2}`}
        diff={diff}
        isOpen={showDiff}
        onClose={() => {
          setShowDiff(false);
          onClose();
        }}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-md border border-border-default bg-surface p-5 shadow-xl space-y-3.5">
        <div className="flex items-center justify-between border-b border-border-subtle pb-3">
          <div className="flex items-center gap-2">
            <GitCompare className="w-4 h-4 text-brand" />
            <h3 className="text-sm font-semibold text-primary">
              Compare Two Releases
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xs p-1 text-muted hover:bg-surface-elevated hover:text-primary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-[11px] font-medium text-secondary mb-1">
              Base Version (Original)
            </label>
            <select
              value={v1}
              onChange={(e) => setV1(Number(e.target.value))}
              className="w-full rounded-xs border border-border-default bg-surface-elevated p-2 text-xs text-primary focus:outline-none focus:border-brand"
            >
              {sorted.map((r) => (
                <option key={`base-${r.version}`} value={r.version}>
                  v{r.version} — {r.comment || 'No comment'} ({new Date(r.released_at).toLocaleDateString()})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-secondary mb-1">
              Target Version (Comparison)
            </label>
            <select
              value={v2}
              onChange={(e) => setV2(Number(e.target.value))}
              className="w-full rounded-xs border border-border-default bg-surface-elevated p-2 text-xs text-primary focus:outline-none focus:border-brand"
            >
              {sorted.map((r) => (
                <option key={`target-${r.version}`} value={r.version}>
                  v{r.version} — {r.comment || 'No comment'} ({new Date(r.released_at).toLocaleDateString()})
                </option>
              ))}
            </select>
          </div>
        </div>

        {isError && (
          <div className="text-xs text-status-danger">
            Failed to compute diff between selected versions.
          </div>
        )}

        <div className="flex justify-end gap-2 border-t border-border-subtle pt-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xs border border-border-default bg-surface px-3 py-1.5 text-xs font-medium text-secondary hover:bg-surface-elevated hover:text-primary transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => setShowDiff(true)}
            className="rounded-xs bg-brand px-3.5 py-1.5 text-xs font-medium text-white hover:bg-brand-hover shadow-xs disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Comparing...' : 'View Diff'}
          </button>
        </div>
      </div>
    </div>
  );
};
