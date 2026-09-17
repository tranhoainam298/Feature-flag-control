import React, { useState } from 'react';
import { TargetingRuleInput } from '../../types';

interface JsonRuleEditorProps {
  rules: TargetingRuleInput[];
  onChange: (rules: TargetingRuleInput[]) => void;
  disabled?: boolean;
}

export const JsonRuleEditor: React.FC<JsonRuleEditorProps> = ({
  rules,
  onChange,
  disabled = false,
}) => {
  const [jsonText, setJsonText] = useState(() => JSON.stringify(rules, null, 2));
  const [error, setError] = useState<string | null>(null);

  const handleApply = () => {
    try {
      const parsed = JSON.parse(jsonText);
      if (!Array.isArray(parsed)) {
        setError('JSON phải là một mảng danh sách rule: [ { priority: 1, ... } ]');
        return;
      }
      setError(null);
      onChange(parsed);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Cú pháp JSON không hợp lệ');
    }
  };

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(jsonText);
      setJsonText(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Cú pháp JSON không hợp lệ');
    }
  };

  return (
    <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)]">
            Chế độ JSON nâng cao
          </h4>
          <p className="text-xs text-[var(--text-tertiary)]">
            Dán hoặc chỉnh sửa trực tiếp mảng JSON rules (chế độ dự phòng kỹ thuật)
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleFormat}
            disabled={disabled}
            className="rounded border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
          >
            Định dạng JSON
          </button>
          <button
            type="button"
            onClick={handleApply}
            disabled={disabled}
            className="rounded bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm"
          >
            Áp dụng thay đổi
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded border border-rose-500/40 bg-rose-500/10 p-2.5 text-xs text-rose-300 font-mono"
        >
          {error}
        </div>
      )}

      <textarea
        value={jsonText}
        disabled={disabled}
        onChange={(e) => {
          setJsonText(e.target.value);
          if (error) setError(null);
        }}
        rows={14}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-3 font-mono text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
        spellCheck={false}
      />
    </div>
  );
};
