import React from 'react';
import { Segment } from '../../types';
import { Users, Trash2, Code2 } from 'lucide-react';

interface SegmentCardProps {
  segment: Segment;
  onDelete: (id: string) => void;
  disabled?: boolean;
}

export const SegmentCard: React.FC<SegmentCardProps> = ({
  segment,
  onDelete,
  disabled = false,
}) => {
  const condCount =
    segment.conditions && Array.isArray(segment.conditions.conditions)
      ? segment.conditions.conditions.length
      : 0;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm hover:border-indigo-500/40 transition-all flex flex-col justify-between">
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
              <Users className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                {segment.name}
              </h4>
              <span className="font-mono text-xs text-indigo-400/90">
                {segment.key}
              </span>
            </div>
          </div>

          <button
            type="button"
            title="Xóa segment"
            disabled={disabled}
            onClick={() => {
              if (window.confirm(`Bạn có chắc muốn xóa segment "${segment.name}"?`)) {
                onDelete(segment.id);
              }
            }}
            className="rounded p-1.5 text-[var(--text-tertiary)] hover:bg-rose-500/10 hover:text-rose-400 transition-colors disabled:opacity-40"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>

        {segment.description && (
          <p className="text-xs text-[var(--text-secondary)] line-clamp-2">
            {segment.description}
          </p>
        )}

        {/* Condition preview */}
        <div className="rounded-lg bg-[var(--surface-sunken)] p-2.5 border border-[var(--border)] text-xs">
          <div className="flex items-center justify-between text-[11px] text-[var(--text-tertiary)] mb-1">
            <span className="flex items-center gap-1 font-medium">
              <Code2 className="w-3 h-3 text-indigo-400" />
              Toán tử: {segment.conditions?.operator || 'AND'}
            </span>
            <span>{condCount} điều kiện</span>
          </div>
          <pre className="max-h-20 overflow-y-auto font-mono text-[11px] text-[var(--text-secondary)]">
            {JSON.stringify(segment.conditions, null, 2)}
          </pre>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-[var(--text-tertiary)] flex justify-between">
        <span>Tạo: {new Date(segment.created_at).toLocaleDateString()}</span>
      </div>
    </div>
  );
};
