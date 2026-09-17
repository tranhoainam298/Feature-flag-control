import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { TargetingRuleInput, Variation } from '../../types';
import { targetingApi } from './api';
import { RuleCard } from './RuleCard';
import { JsonRuleEditor } from './JsonRuleEditor';

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
      // Map to TargetingRuleInput with sorted priority
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
      setSuccessMessage('Đã lưu thành công các quy tắc phân phối!');
      setErrorMessage(null);
      setTimeout(() => setSuccessMessage(null), 4000);
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Không thể lưu quy tắc. Vui lòng kiểm tra lại điều kiện và tỉ lệ phân phối.';
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

    // Recalculate sequential priorities 1..N
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

    // Frontend pre-check: Each rule distribution must sum to 100
    for (let i = 0; i < rules.length; i++) {
      const sum = Math.round(
        rules[i].distribution.reduce((acc, d) => acc + (d.weight || 0), 0) * 10
      ) / 10;
      if (Math.abs(sum - 100) > 0.1) {
        setErrorMessage(
          `Quy tắc #${rules[i].priority} có tổng phân phối là ${sum}%. Phải bằng đúng 100% trước khi lưu!`
        );
        return;
      }
    }

    saveMutation.mutate(rules);
  };

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-[var(--text-tertiary)]">
        Đang tải quy tắc targeting...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-400">
        Lỗi tải quy tắc: {error instanceof Error ? error.message : 'Không xác định'}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top action bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setMode('visual')}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === 'visual'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'border border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            Trình dựng quy tắc
          </button>
          <button
            type="button"
            onClick={() => setMode('json')}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === 'json'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'border border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            JSON nâng cao
          </button>
        </div>

        <div className="flex items-center gap-2">
          {mode === 'visual' && (
            <button
              type="button"
              onClick={handleAddRule}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-hover)] shadow-sm"
            >
              <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              <span>Thêm quy tắc</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Đang lưu...' : 'Lưu tất cả quy tắc'}
          </button>
        </div>
      </div>

      {/* Messages */}
      {successMessage && (
        <div
          role="status"
          className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-400"
        >
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div
          role="alert"
          className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-400"
        >
          {errorMessage}
        </div>
      )}

      {/* Visual or JSON Mode */}
      {mode === 'visual' ? (
        <div className="space-y-4">
          {rules.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--border)] p-8 text-center">
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-400 mb-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <p className="text-sm font-medium text-[var(--text-primary)]">Chưa có quy tắc targeting nào</p>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                Tất cả đánh giá sẽ rơi về variation mặc định của flag này.
              </p>
              <button
                type="button"
                onClick={handleAddRule}
                className="mt-4 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
              >
                Tạo quy tắc đầu tiên
              </button>
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
