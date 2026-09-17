import React from 'react';

export interface SkeletonTableProps {
  rows?: number;
  columns?: number;
}

export const SkeletonTable: React.FC<SkeletonTableProps> = ({ rows = 5, columns = 5 }) => {
  return (
    <div className="w-full border border-border-subtle rounded-md overflow-hidden animate-pulse">
      {/* Table Header */}
      <div className="bg-surface-elevated border-b border-border-subtle p-3 flex gap-4">
        {Array.from({ length: columns }).map((_, i) => (
          <div key={i} className="h-4 bg-surface-active rounded-xs flex-1" />
        ))}
      </div>
      {/* Table Rows */}
      <div className="divide-y divide-border-subtle bg-surface">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="p-4 flex items-center gap-4">
            {Array.from({ length: columns }).map((_, c) => (
              <div
                key={c}
                className="h-3.5 bg-surface-hover rounded-xs"
                style={{ width: `${Math.max(40, 90 - c * 12)}%`, flex: 1 }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};
