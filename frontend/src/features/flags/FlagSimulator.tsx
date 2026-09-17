import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { flagApi } from './api';
import { SimulateResponse } from '../../types';
import { Play, Plus, Trash2, CheckCircle, XCircle, Terminal } from 'lucide-react';
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
    <div className="space-y-4">
      {/* Context Input */}
      <div className="border border-border-subtle rounded-md overflow-hidden">
        <div className="px-4 py-2 border-b border-border-subtle bg-surface-elevated flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-muted" />
            <span className="text-[11px] font-semibold text-primary">Evaluation Context</span>
            <span className="text-[10px] text-muted">— {envName}</span>
          </div>
          <Button size="sm" variant="ghost" onClick={addEntry} leftIcon={<Plus className="w-3 h-3" />} className="h-6 text-[11px]">
            Add
          </Button>
        </div>

        <div className="p-3 space-y-1.5 bg-surface">
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center gap-1.5">
              <input
                type="text"
                placeholder="key"
                value={entry.key}
                onChange={(e) => updateEntry(entry.id, 'key', e.target.value)}
                className="flex-1 bg-surface-elevated text-primary text-xs px-2.5 py-1.5 rounded-sm border border-border-subtle font-mono focus:border-brand focus-visible:outline-none"
                aria-label="Attribute name"
              />
              <input
                type="text"
                placeholder="value"
                value={entry.value}
                onChange={(e) => updateEntry(entry.id, 'value', e.target.value)}
                className="flex-1 bg-surface-elevated text-primary text-xs px-2.5 py-1.5 rounded-sm border border-border-subtle font-mono focus:border-brand focus-visible:outline-none"
                aria-label="Attribute value"
              />
              <button
                type="button"
                onClick={() => removeEntry(entry.id)}
                aria-label="Remove attribute"
                className="p-1 text-muted hover:text-status-danger rounded-xs transition-colors shrink-0"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>

        <div className="px-3 py-2.5 border-t border-border-subtle bg-surface">
          <Button
            variant="primary"
            size="sm"
            onClick={() => simulateMutation.mutate()}
            isLoading={simulateMutation.isPending}
            leftIcon={<Play className="w-3.5 h-3.5" />}
          >
            Run Evaluation Trace
          </Button>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="border border-border-subtle rounded-md overflow-hidden animate-in fade-in duration-200">
          <div className="px-4 py-2 border-b border-border-subtle bg-surface-elevated">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider">Evaluation Result</span>
          </div>

          <div className="p-3 bg-surface">
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="bg-surface-elevated px-3 py-2.5 rounded-sm border border-border-subtle">
                <span className="text-[10px] text-muted font-mono block mb-1">RESOLVED VALUE</span>
                <div className="text-sm font-bold font-mono text-primary">
                  {typeof result.value === 'object' ? JSON.stringify(result.value) : String(result.value)}
                </div>
              </div>
              <div className="bg-surface-elevated px-3 py-2.5 rounded-sm border border-border-subtle">
                <span className="text-[10px] text-muted font-mono block mb-1">VARIANT</span>
                <div className="text-sm font-semibold font-mono text-brand">{result.variant}</div>
              </div>
              <div className="bg-surface-elevated px-3 py-2.5 rounded-sm border border-border-subtle">
                <span className="text-[10px] text-muted font-mono block mb-1">REASON</span>
                <div className="mt-0.5">
                  <Badge variant={getReasonBadgeVariant(result.reason)} size="sm">
                    {result.reason}
                  </Badge>
                </div>
              </div>
            </div>

            {/* Engine Trace */}
            {result.trace && result.trace.length > 0 && (
              <div>
                <div className="text-[10px] font-mono text-muted uppercase tracking-wider mb-2">
                  Engine Trace — {result.trace.length} rule{result.trace.length !== 1 ? 's' : ''} evaluated
                </div>
                <div className="border border-border-subtle rounded-sm overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-surface-active/40 border-b border-border-subtle">
                      <tr className="text-[9px] font-mono text-muted uppercase tracking-wider">
                        <th className="px-3 py-1.5 w-12">#</th>
                        <th className="px-3 py-1.5">Rule</th>
                        <th className="px-3 py-1.5 w-24">Status</th>
                        <th className="px-3 py-1.5">Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-subtle font-mono text-[11px]">
                      {result.trace.map((tr, idx) => (
                        <tr key={idx} className={tr.matched ? 'bg-status-success-bg' : ''}>
                          <td className="px-3 py-1.5 text-muted">{tr.priority ?? idx + 1}</td>
                          <td className="px-3 py-1.5 text-primary">{tr.description || 'Targeting rule'}</td>
                          <td className="px-3 py-1.5">
                            {tr.matched ? (
                              <span className="inline-flex items-center gap-1 text-brand font-semibold">
                                <CheckCircle className="w-3 h-3" /> MATCH
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-muted">
                                <XCircle className="w-3 h-3" /> SKIP
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-1.5 text-muted">{tr.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
