import React, { useState } from 'react';
import { TargetingRuleInput } from '../../types';
import { AlertCircle } from 'lucide-react';

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
        setError('JSON payload must be an array of rule specifications: [ { priority: 1, ... } ]');
        return;
      }
      setError(null);
      onChange(parsed);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Invalid JSON syntax');
    }
  };

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(jsonText);
      setJsonText(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Invalid JSON syntax');
    }
  };

  return (
    <div className="space-y-3 rounded-md border border-border-default bg-surface p-3.5 shadow-xs">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-xs font-semibold text-primary">
            Advanced Rule Specification (JSON)
          </h4>
          <p className="text-[11px] text-muted">
            Directly inspect or edit the underlying rule definitions array in raw JSON.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleFormat}
            disabled={disabled}
            className="rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1 text-xs text-secondary hover:text-primary hover:bg-surface-elevated/80 transition-colors"
          >
            Format JSON
          </button>
          <button
            type="button"
            onClick={handleApply}
            disabled={disabled}
            className="rounded-xs bg-brand px-3 py-1 text-xs font-medium text-white hover:bg-brand-hover shadow-xs transition-colors"
          >
            Apply Changes
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-xs border border-status-danger/30 bg-status-danger/10 p-2 text-xs text-status-danger font-mono"
        >
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
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
        className="w-full rounded-xs border border-border-default bg-surface-elevated p-3 font-mono text-xs text-primary focus:border-brand focus-visible:outline-none"
        spellCheck={false}
      />
    </div>
  );
};
