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
        title={`So sánh phiên bản v${v1} → v${v2}`}
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
      <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <div className="flex items-center gap-2">
            <GitCompare className="w-4 h-4 text-indigo-400" />
            <h3 className="text-base font-semibold text-[var(--text-primary)]">
              So sánh 2 phiên bản Release
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Phiên bản gốc (Base version)
            </label>
            <select
              value={v1}
              onChange={(e) => setV1(Number(e.target.value))}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-2 text-xs text-[var(--text-primary)] focus:outline-none"
            >
              {sorted.map((r) => (
                <option key={`base-${r.version}`} value={r.version}>
                  v{r.version} — {r.comment || 'Không có ghi chú'} ({new Date(r.released_at).toLocaleDateString()})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Phiên bản so sánh (Target version)
            </label>
            <select
              value={v2}
              onChange={(e) => setV2(Number(e.target.value))}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-2 text-xs text-[var(--text-primary)] focus:outline-none"
            >
              {sorted.map((r) => (
                <option key={`target-${r.version}`} value={r.version}>
                  v{r.version} — {r.comment || 'Không có ghi chú'} ({new Date(r.released_at).toLocaleDateString()})
                </option>
              ))}
            </select>
          </div>
        </div>

        {isError && (
          <div className="text-xs text-rose-400">
            Không thể so sánh 2 phiên bản này.
          </div>
        )}

        <div className="flex justify-end gap-2 border-t border-[var(--border)] pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
          >
            Hủy
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => setShowDiff(true)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm disabled:opacity-50"
          >
            {isLoading ? 'Đang so sánh...' : 'Xem khác biệt (Diff)'}
          </button>
        </div>
      </div>
    </div>
  );
};
