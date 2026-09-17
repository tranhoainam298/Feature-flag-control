import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { flagApi } from './api';
import { SimulateResponse } from '../../types';
import { Play, Plus, Trash2, CheckCircle, XCircle, Sparkles } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';

interface ContextEntry {
  id: string;
  key: string;
  value: string;
}

interface Props {
  flagId: string;
  envId: string;
  envName: string;
}

export const FlagSimulator: React.FC<Props> = ({ flagId, envId, envName }) => {
  const [entries, setEntries] = useState<ContextEntry[]>([
    { id: '1', key: 'country', value: 'VN' },
    { id: '2', key: 'plan', value: 'premium' },
  ]);

  const addEntry = () => {
    setEntries((prev) => [...prev, { id: Math.random().toString(), key: '', value: '' }]);
  };

  const removeEntry = (id: string) => {
    setEntries((prev) => prev.filter((e) => e.id !== id));
  };

  const updateEntry = (id: string, field: 'key' | 'value', val: string) => {
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, [field]: val } : e)));
  };

  const setPreset = (preset: Record<string, string>) => {
    setEntries(
      Object.entries(preset).map(([k, v]) => ({
        id: Math.random().toString(),
        key: k,
        value: v,
      }))
    );
  };

  const simulateMutation = useMutation<SimulateResponse>({
    mutationFn: () => {
      const context: Record<string, unknown> = {};
      for (const entry of entries) {
        if (!entry.key.trim()) continue;
        const val = entry.value.trim();
        if (val === 'true') context[entry.key] = true;
        else if (val === 'false') context[entry.key] = false;
        else if (!isNaN(Number(val)) && val !== '') context[entry.key] = Number(val);
        else context[entry.key] = val;
      }
      return flagApi.simulateEvaluation(flagId, envId, context);
    },
  });

  const getReasonBadgeVariant = (reason: string) => {
    if (reason === 'TARGETING_MATCH' || reason === 'RULE_MATCH') return 'success';
    if (reason === 'DISABLED') return 'danger';
    if (reason === 'DEFAULT') return 'info';
    return 'default';
  };

  const result = simulateMutation.data;

  return (
    <div className="border border-border-default rounded-lg overflow-hidden bg-surface mb-8">
      <div className="p-4 border-b border-border-subtle bg-surface-elevated flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-primary flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-brand" />
            Evaluation Simulator
          </h3>
          <p className="text-xs text-muted">
            Simulate runtime flag evaluation for environment: <span className="text-primary font-medium">{envName}</span>
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setPreset({ country: 'VN', plan: 'premium' })}
            className="text-[11px] h-7"
          >
            Preset: VN Premium
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setPreset({ country: 'US', plan: 'free' })}
            className="text-[11px] h-7"
          >
            Preset: US Free
          </Button>
        </div>
      </div>

      <div className="p-5 space-y-6">
        {/* Context Input Grid */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-secondary">
              Evaluation Context (Key-Value)
            </label>
            <Button size="sm" variant="ghost" onClick={addEntry} leftIcon={<Plus className="w-3.5 h-3.5" />} className="h-7 text-xs">
              Add Attribute
            </Button>
          </div>

          <div className="space-y-2">
            {entries.map((entry) => (
              <div key={entry.id} className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Attribute (e.g. country)"
                  value={entry.key}
                  onChange={(e) => updateEntry(entry.id, 'key', e.target.value)}
                  className="flex-1 bg-surface-elevated text-primary text-xs px-3 py-1.5 rounded-md border border-border-default font-mono focus:border-brand focus-visible:outline-none"
                  aria-label="Context attribute name"
                />
                <input
                  type="text"
                  placeholder="Value (e.g. VN)"
                  value={entry.value}
                  onChange={(e) => updateEntry(entry.id, 'value', e.target.value)}
                  className="flex-1 bg-surface-elevated text-primary text-xs px-3 py-1.5 rounded-md border border-border-default font-mono focus:border-brand focus-visible:outline-none"
                  aria-label="Context attribute value"
                />
                <button
                  type="button"
                  onClick={() => removeEntry(entry.id)}
                  aria-label="Remove attribute"
                  className="p-1.5 text-muted hover:text-status-danger rounded-sm transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <Button
              variant="primary"
              onClick={() => simulateMutation.mutate()}
              isLoading={simulateMutation.isPending}
              leftIcon={<Play className="w-4 h-4" />}
            >
              Run Simulation
            </Button>
          </div>
        </div>

        {/* Results Section */}
        {result && (
          <div className="pt-5 border-t border-border-subtle animate-in fade-in duration-200">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-secondary mb-3">
              Simulation Result
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
              <div className="bg-surface-elevated p-3 rounded-md border border-border-subtle">
                <span className="text-[10px] text-muted uppercase font-mono">Resolved Value</span>
                <div className="text-sm font-bold font-mono text-primary mt-1">
                  {typeof result.value === 'object' ? JSON.stringify(result.value) : String(result.value)}
                </div>
              </div>
              <div className="bg-surface-elevated p-3 rounded-md border border-border-subtle">
                <span className="text-[10px] text-muted uppercase font-mono">Variant</span>
                <div className="text-sm font-semibold font-mono text-brand mt-1">{result.variant}</div>
              </div>
              <div className="bg-surface-elevated p-3 rounded-md border border-border-subtle">
                <span className="text-[10px] text-muted uppercase font-mono">Reason</span>
                <div className="mt-1">
                  <Badge variant={getReasonBadgeVariant(result.reason)} size="md">
                    {result.reason}
                  </Badge>
                </div>
              </div>
            </div>

            {/* Trace Table */}
            {result.trace && result.trace.length > 0 && (
              <div>
                <h5 className="text-[11px] font-semibold text-secondary uppercase mb-2">
                  Rules Evaluation Trace ({result.trace.length} evaluated)
                </h5>
                <div className="border border-border-subtle rounded-md overflow-hidden bg-surface-elevated">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-surface-active/50 border-b border-border-subtle text-[10px] uppercase font-mono text-muted">
                      <tr>
                        <th className="p-2.5">Priority</th>
                        <th className="p-2.5">Rule Description</th>
                        <th className="p-2.5">Status</th>
                        <th className="p-2.5">Outcome Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-subtle text-secondary font-mono text-[11px]">
                      {result.trace.map((tr, idx) => (
                        <tr key={idx} className={tr.matched ? 'bg-flag-on-bg/20' : ''}>
                          <td className="p-2.5 text-muted">#{tr.priority ?? idx + 1}</td>
                          <td className="p-2.5 text-primary">{tr.description || 'Targeting condition'}</td>
                          <td className="p-2.5">
                            {tr.matched ? (
                              <span className="inline-flex items-center gap-1 text-flag-on font-semibold">
                                <CheckCircle className="w-3.5 h-3.5" /> MATCHED
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-muted">
                                <XCircle className="w-3.5 h-3.5" /> SKIPPED
                              </span>
                            )}
                          </td>
                          <td className="p-2.5 text-muted">{tr.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
