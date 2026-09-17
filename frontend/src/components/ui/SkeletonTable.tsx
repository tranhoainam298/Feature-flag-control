import React from 'react';

interface Props {
  rows?: number;
  columns?: number;
}

export const SkeletonTable: React.FC<Props> = ({ rows = 5, columns = 5 }) => {
  return (
    <div className="border border-border-subtle rounded-md overflow-hidden">
      {/* Header */}
      <div className="bg-surface-elevated border-b border-border-subtle px-4 py-2.5 flex gap-6">
        {Array.from({ length: columns }).map((_, i) => (
          <div key={`h-${i}`} className="skeleton h-3 rounded-xs" style={{ width: `${60 + i * 20}px` }} />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={`r-${r}`} className="px-4 py-3 border-b border-border-subtle last:border-0 flex gap-6 items-center">
          {Array.from({ length: columns }).map((_, c) => (
            <div
              key={`r-${r}-c-${c}`}
              className="skeleton h-3 rounded-xs"
              style={{ width: c === 0 ? '140px' : `${50 + c * 15}px` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
};
