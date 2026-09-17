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
    <div className="rounded-md border border-border-default bg-surface p-3.5 shadow-xs hover:border-border-hover transition-colors flex flex-col justify-between">
      <div className="space-y-2.5">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-xs bg-brand/10 text-brand border border-brand/20">
              <Users className="w-3.5 h-3.5" />
            </div>
            <div>
              <h4 className="text-xs font-semibold text-primary">
                {segment.name}
              </h4>
              <span className="font-mono text-[11px] text-muted">
                {segment.key}
              </span>
            </div>
          </div>

          <button
            type="button"
            title="Delete segment"
            disabled={disabled}
            onClick={() => {
              if (window.confirm(`Are you sure you want to delete segment "${segment.name}"?`)) {
                onDelete(segment.id);
              }
            }}
            className="rounded-xs p-1 text-muted hover:bg-status-danger/10 hover:text-status-danger transition-colors disabled:opacity-40"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>

        {segment.description && (
          <p className="text-xs text-secondary line-clamp-2">
            {segment.description}
          </p>
        )}

        {/* Condition preview */}
        <div className="rounded-xs bg-surface-elevated p-2 border border-border-subtle text-xs">
          <div className="flex items-center justify-between text-[11px] text-muted mb-1">
            <span className="flex items-center gap-1 font-medium text-secondary">
              <Code2 className="w-3 h-3 text-brand" />
              Operator: <span className="font-mono font-bold text-primary">{segment.conditions?.operator || 'AND'}</span>
            </span>
            <span className="font-mono text-[11px]">{condCount} {condCount === 1 ? 'clause' : 'clauses'}</span>
          </div>
          <pre className="max-h-20 overflow-y-auto font-mono text-[11px] text-secondary">
            {JSON.stringify(segment.conditions, null, 2)}
          </pre>
        </div>
      </div>

      <div className="mt-3 pt-2.5 border-t border-border-subtle text-[11px] text-muted flex justify-between font-mono">
        <span>Created: {new Date(segment.created_at).toLocaleDateString()}</span>
      </div>
    </div>
  );
};
