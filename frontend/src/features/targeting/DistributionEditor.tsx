import React from 'react';
import { DistributionItem, Variation } from '../../types';
import { AlertTriangle } from 'lucide-react';

interface DistributionEditorProps {
  variations: Variation[];
  distribution: DistributionItem[];
  onChange: (items: DistributionItem[]) => void;
  disabled?: boolean;
}

export const VARIATION_COLORS = [
  { bg: 'bg-sky-500', text: 'text-sky-500', border: 'border-sky-500', hex: '#0284c7' },
  { bg: 'bg-violet-500', text: 'text-violet-500', border: 'border-violet-500', hex: '#8b5cf6' },
  { bg: 'bg-amber-500', text: 'text-amber-500', border: 'border-amber-500', hex: '#f59e0b' },
  { bg: 'bg-emerald-500', text: 'text-emerald-500', border: 'border-emerald-500', hex: '#10b981' },
  { bg: 'bg-rose-500', text: 'text-rose-500', border: 'border-rose-500', hex: '#f43f5e' },
  { bg: 'bg-indigo-500', text: 'text-indigo-500', border: 'border-indigo-500', hex: '#6366f1' },
];

export const DistributionEditor: React.FC<DistributionEditorProps> = ({
  variations,
  distribution,
  onChange,
  disabled = false,
}) => {
  // Ensure all variations have an entry
  const getWeight = (varId: string): number => {
    const item = distribution.find((d) => d.variation_id === varId);
    return item ? item.weight : 0;
  };

  const handleWeightChange = (varId: string, newWeight: number) => {
    const val = Math.max(0, Math.min(100, isNaN(newWeight) ? 0 : newWeight));
    const next = variations.map((v) => ({
      variation_id: v.id,
      weight: v.id === varId ? val : getWeight(v.id),
    }));
    onChange(next);
  };

  const handleEvenSplit = () => {
    if (variations.length === 0) return;
    const base = Math.floor((100 / variations.length) * 10) / 10;
    const remainder = Math.round((100 - base * variations.length) * 10) / 10;
    const next = variations.map((v, i) => ({
      variation_id: v.id,
      weight: i === 0 ? Math.round((base + remainder) * 10) / 10 : base,
    }));
    onChange(next);
  };

  const handleSetAllTo = (varId: string) => {
    const next = variations.map((v) => ({
      variation_id: v.id,
      weight: v.id === varId ? 100 : 0,
    }));
    onChange(next);
  };

  const totalWeight = Math.round(
    variations.reduce((sum, v) => sum + getWeight(v.id), 0) * 10
  ) / 10;

  const isInvalidTotal = Math.abs(totalWeight - 100) > 0.01;

  return (
    <div className="space-y-2.5 rounded-sm border border-border-default bg-surface-elevated/40 p-2.5 text-xs">
      <div className="flex items-center justify-between">
        <span className="font-medium text-secondary text-[11px] uppercase tracking-wider">
          Rollout Distribution
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleEvenSplit}
            disabled={disabled}
            className="rounded-xs border border-border-default bg-surface px-2 py-0.5 text-[11px] text-secondary hover:text-primary hover:bg-surface-elevated disabled:opacity-50 transition-colors"
          >
            Equal Split
          </button>
          <span
            className={`rounded-xs px-2 py-0.5 text-[11px] font-mono font-semibold ${
              isInvalidTotal
                ? 'bg-status-danger/10 text-status-danger border border-status-danger/30'
                : 'bg-status-success/10 text-status-success border border-status-success/30'
            }`}
          >
            Total: {totalWeight}%
          </span>
        </div>
      </div>

      {/* Segmented Progress Bar */}
      <div className="w-full space-y-1.5">
        <div className="h-3.5 w-full rounded-xs overflow-hidden flex bg-surface-elevated border border-border-default shadow-inner">
          {variations.map((v, i) => {
            const w = getWeight(v.id);
            if (w <= 0) return null;
            const color = VARIATION_COLORS[i % VARIATION_COLORS.length];
            return (
              <div
                key={v.id}
                style={{ width: `${w}%` }}
                title={`${v.key}: ${w}%`}
                className={`${color.bg} h-full transition-all duration-200 flex items-center justify-center text-[9px] font-mono text-white font-medium truncate px-1`}
              >
                {w >= 14 ? `${v.key} ${w}%` : w >= 7 ? `${w}%` : ''}
              </div>
            );
          })}
        </div>
        {/* Legend */}
        <div className="flex flex-wrap items-center gap-3 px-0.5">
          {variations.map((v, i) => {
            const w = getWeight(v.id);
            const color = VARIATION_COLORS[i % VARIATION_COLORS.length];
            return (
              <div key={v.id} className="flex items-center gap-1.5 text-[10px] font-mono">
                <span className={`w-2 h-2 rounded-full ${color.bg}`} />
                <span className="text-secondary">{v.key}</span>
                <span className="font-semibold text-primary">{w}%</span>
              </div>
            );
          })}
        </div>
      </div>

      {isInvalidTotal && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-xs border border-status-danger/30 bg-status-danger/10 px-2.5 py-1.5 text-xs text-status-danger font-medium"
        >
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>Total weight must sum to 100% (currently {totalWeight}%).</span>
        </div>
      )}

      <div className="space-y-1.5">
        {variations.map((v, i) => {
          const w = getWeight(v.id);
          const color = VARIATION_COLORS[i % VARIATION_COLORS.length];
          return (
            <div
              key={v.id}
              className="flex items-center gap-3 rounded-xs bg-surface px-2.5 py-1.5 border border-border-subtle"
            >
              <div className="min-w-28 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${color.bg}`} />
                  <span className="font-semibold text-xs text-primary font-mono">
                    {v.key}
                  </span>
                  <button
                    type="button"
                    title={`Set 100% to ${v.key}`}
                    onClick={() => handleSetAllTo(v.id)}
                    disabled={disabled}
                    className="text-[10px] text-brand hover:underline font-mono"
                  >
                    100%
                  </button>
                </div>
                <div className="text-[11px] font-mono text-muted truncate max-w-[200px]">
                  {typeof v.value === 'object' ? JSON.stringify(v.value) : String(v.value)}
                </div>
              </div>

              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={w}
                disabled={disabled}
                onChange={(e) => handleWeightChange(v.id, parseFloat(e.target.value))}
                className="flex-1 accent-brand h-1.5 bg-surface-elevated rounded cursor-pointer disabled:cursor-not-allowed"
              />

              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={w}
                  disabled={disabled}
                  onChange={(e) => handleWeightChange(v.id, parseFloat(e.target.value))}
                  className="w-14 rounded-xs border border-border-default bg-surface-elevated px-2 py-1 text-right text-xs font-mono text-primary focus:border-brand focus-visible:outline-none"
                />
                <span className="text-[11px] text-muted font-mono">%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
