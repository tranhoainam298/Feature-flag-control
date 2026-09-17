import React from 'react';
import { DistributionItem, Variation } from '../../types';

interface DistributionEditorProps {
  variations: Variation[];
  distribution: DistributionItem[];
  onChange: (items: DistributionItem[]) => void;
  disabled?: boolean;
}

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
    <div className="space-y-3 rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--text-primary)]">
          Phân phối Variation (Rollout)
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleEvenSplit}
            disabled={disabled}
            className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] disabled:opacity-50"
          >
            Chia đều
          </button>
          <span
            className={`rounded px-2 py-0.5 text-xs font-semibold ${
              isInvalidTotal
                ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            }`}
          >
            Tổng: {totalWeight}%
          </span>
        </div>
      </div>

      {isInvalidTotal && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300 font-medium"
        >
          <svg className="w-4 h-4 shrink-0 text-rose-400" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          <span>Cảnh báo: Tổng tỉ lệ phân phối là {totalWeight}%. Phải bằng đúng 100%!</span>
        </div>
      )}

      <div className="space-y-2">
        {variations.map((v) => {
          const w = getWeight(v.id);
          return (
            <div
              key={v.id}
              className="flex items-center gap-3 rounded bg-[var(--surface)] px-3 py-2 border border-[var(--border)]"
            >
              <div className="min-w-28 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="font-medium text-xs text-[var(--text-primary)]">
                    {v.key}
                  </span>
                  <button
                    type="button"
                    title={`Gán 100% cho ${v.key}`}
                    onClick={() => handleSetAllTo(v.id)}
                    disabled={disabled}
                    className="text-[10px] text-[var(--text-tertiary)] hover:text-indigo-400 underline"
                  >
                    100%
                  </button>
                </div>
                <div className="text-[11px] font-mono text-[var(--text-tertiary)] truncate">
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
                className="flex-1 accent-indigo-500 h-1.5 bg-[var(--surface-sunken)] rounded cursor-pointer disabled:cursor-not-allowed"
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
                  className="w-16 rounded border border-[var(--border)] bg-[var(--surface-sunken)] px-2 py-1 text-right text-xs font-mono text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
                />
                <span className="text-xs text-[var(--text-tertiary)]">%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
