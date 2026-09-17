import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { TargetingRuleInput, Variation } from '../../types';
import { targetingApi } from './api';
import { RuleCard } from './RuleCard';
import { JsonRuleEditor } from './JsonRuleEditor';
import { Plus, Save, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/Button';

interface RuleBuilderProps {
  flagId: string;
  envId: string;
  variations: Variation[];
}

export const RuleBuilder: React.FC<RuleBuilderProps> = ({
  flagId,
  envId,
  variations,
}) => {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<'visual' | 'json'>('visual');
  const [rules, setRules] = useState<TargetingRuleInput[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    data: remoteRules,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['targeting-rules', flagId, envId],
    queryFn: () => targetingApi.listTargetingRules(flagId, envId),
    enabled: !!flagId && !!envId,
  });

  useEffect(() => {
    if (remoteRules) {
      const mapped = [...remoteRules]
        .sort((a, b) => a.priority - b.priority)
        .map((r) => ({
          priority: r.priority,
          description: r.description,
          segment_id: r.segment_id,
          conditions: r.conditions,
          distribution: r.distribution,
        }));
      setRules(mapped);
    }
  }, [remoteRules]);

  const saveMutation = useMutation({
    mutationFn: (newRules: TargetingRuleInput[]) =>
      targetingApi.updateTargetingRules(flagId, envId, newRules),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['targeting-rules', flagId, envId] });
      setSuccessMessage('Targeting rules saved successfully.');
      setErrorMessage(null);
      setTimeout(() => setSuccessMessage(null), 4000);
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Failed to save rules. Check conditions and distribution weights.';
      setErrorMessage(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
      setSuccessMessage(null);
    },
  });

  const handleAddRule = () => {
    const defaultDist = variations.map((v, i) => ({
      variation_id: v.id,
      weight: i === 0 ? 100 : 0,
    }));

    const newRule: TargetingRuleInput = {
      priority: rules.length + 1,
      description: '',
      segment_id: null,
      conditions: {
        operator: 'AND',
        conditions: [{ attribute: 'user_id', operator: 'EQ', value: '' }],
      },
      distribution: defaultDist,
    };

    setRules([...rules, newRule]);
  };

  const handleUpdateRule = (index: number, updated: TargetingRuleInput) => {
    const next = [...rules];
    next[index] = updated;
    setRules(next);
  };

  const handleMove = (index: number, direction: 'up' | 'down') => {
    const targetIdx = direction === 'up' ? index - 1 : index + 1;
    if (targetIdx < 0 || targetIdx >= rules.length) return;

    const next = [...rules];
    const temp = next[index];
    next[index] = next[targetIdx];
    next[targetIdx] = temp;

    const reordered = next.map((r, i) => ({ ...r, priority: i + 1 }));
    setRules(reordered);
  };

  const handleDeleteRule = (index: number) => {
    const filtered = rules.filter((_, i) => i !== index);
    const reordered = filtered.map((r, i) => ({ ...r, priority: i + 1 }));
    setRules(reordered);
  };

  const handleSave = () => {
    setErrorMessage(null);

    for (let i = 0; i < rules.length; i++) {
      const sum = Math.round(
        rules[i].distribution.reduce((acc, d) => acc + (d.weight || 0), 0) * 10
      ) / 10;
      if (Math.abs(sum - 100) > 0.1) {
        setErrorMessage(
          `Rule #${rules[i].priority} distribution sums to ${sum}%. Must equal exactly 100%.`
        );
        return;
      }
    }

    saveMutation.mutate(rules);
  };

  if (isLoading) {
    return (
      <div className="flex h-32 items-center justify-center text-xs text-muted gap-2">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Loading targeting rules…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-sm border border-status-danger-border bg-status-danger-bg px-3 py-2.5 text-xs text-status-danger">
        Error loading rules: {error instanceof Error ? error.message : 'Unknown error'}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Mode Switch & Actions */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-0.5 bg-surface-active/40 p-0.5 rounded-sm border border-border-subtle">
          <button
            type="button"
            onClick={() => setMode('visual')}
            className={`px-2.5 py-1 rounded-xs text-[11px] font-medium transition-colors ${
              mode === 'visual'
                ? 'bg-surface-elevated text-primary shadow-sm border border-border-default'
                : 'text-muted hover:text-secondary'
            }`}
          >
            Visual Builder
          </button>
          <button
            type="button"
            onClick={() => setMode('json')}
            className={`px-2.5 py-1 rounded-xs text-[11px] font-medium transition-colors ${
              mode === 'json'
                ? 'bg-surface-elevated text-primary shadow-sm border border-border-default'
                : 'text-muted hover:text-secondary'
            }`}
          >
            JSON Editor
          </button>
        </div>

        <div className="flex items-center gap-2">
          {mode === 'visual' && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleAddRule}
              leftIcon={<Plus className="w-3 h-3" />}
            >
              Add Rule
            </Button>
          )}

          <Button
            variant="primary"
            size="sm"
            onClick={handleSave}
            isLoading={saveMutation.isPending}
            leftIcon={<Save className="w-3 h-3" />}
          >
            Save Rules
          </Button>
        </div>
      </div>

      {/* Messages */}
      {successMessage && (
        <div
          role="status"
          className="rounded-sm border border-status-success-border bg-status-success-bg px-3 py-2 text-xs text-status-success"
        >
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div
          role="alert"
          className="rounded-sm border border-status-danger-border bg-status-danger-bg px-3 py-2 text-xs text-status-danger"
        >
          {errorMessage}
        </div>
      )}

      {/* Visual or JSON Mode */}
      {mode === 'visual' ? (
        <div className="space-y-3">
          {rules.length === 0 ? (
            <div className="border border-border-subtle border-dashed rounded-md px-8 py-10 text-center">
              <p className="text-xs font-medium text-primary mb-1">No targeting rules</p>
              <p className="text-[11px] text-muted mb-4">
                All evaluations will fall through to the default variation.
              </p>
              <Button
                variant="primary"
                size="sm"
                onClick={handleAddRule}
                leftIcon={<Plus className="w-3 h-3" />}
              >
                Create First Rule
              </Button>
            </div>
          ) : (
            rules.map((rule, idx) => (
              <RuleCard
                key={`rule-${idx}`}
                rule={rule}
                index={idx}
                totalRules={rules.length}
                variations={variations}
                onUpdate={(upd) => handleUpdateRule(idx, upd)}
                onMoveUp={() => handleMove(idx, 'up')}
                onMoveDown={() => handleMove(idx, 'down')}
                onDelete={() => handleDeleteRule(idx)}
                disabled={saveMutation.isPending}
              />
            ))
          )}
        </div>
      ) : (
        <JsonRuleEditor
          rules={rules}
          onChange={(newRules) => {
            setRules(newRules);
            setMode('visual');
          }}
          disabled={saveMutation.isPending}
        />
      )}
    </div>
  );
};
