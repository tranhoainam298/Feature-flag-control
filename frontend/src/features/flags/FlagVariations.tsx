import React from 'react';
import { Variation } from '../../types';

interface Props {
  variations: Variation[];
}

export const FlagVariations: React.FC<Props> = ({ variations }) => {
  return (
    <div className="border border-border-default rounded-lg overflow-hidden bg-surface mb-6">
      <div className="p-4 border-b border-border-subtle bg-surface-elevated flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-primary">Variations</h3>
          <p className="text-xs text-muted">
            The possible values this feature flag can resolve to during evaluation.
          </p>
        </div>
        <span className="font-mono text-xs text-secondary">{variations.length} defined</span>
      </div>

      <div className="divide-y divide-border-subtle">
        {variations.map((v, idx) => (
          <div key={v.id || idx} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-semibold text-primary">{v.key}</span>
                {v.description && <span className="text-xs text-muted">— {v.description}</span>}
              </div>
              <div className="mt-1.5 font-mono text-xs bg-surface-elevated px-2.5 py-1.5 rounded-sm border border-border-subtle inline-block text-secondary">
                {typeof v.value === 'object' ? JSON.stringify(v.value) : String(v.value)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
