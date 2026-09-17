import React from 'react';
import { ConditionClause } from '../../types';
import { Trash2 } from 'lucide-react';

export const OPERATORS = [
  { value: 'EQ', label: 'Equals (==)' },
  { value: 'NEQ', label: 'Not Equals (!=)' },
  { value: 'IN', label: 'In List (e.g. ["VN", "US"])' },
  { value: 'NOT_IN', label: 'Not In List' },
  { value: 'CONTAINS', label: 'Contains substring' },
  { value: 'STARTS_WITH', label: 'Starts With' },
  { value: 'ENDS_WITH', label: 'Ends With' },
  { value: 'GT', label: 'Greater Than (>)' },
  { value: 'LT', label: 'Less Than (<)' },
  { value: 'GTE', label: 'Greater or Equal (>=)' },
  { value: 'LTE', label: 'Less or Equal (<=)' },
  { value: 'IS_TRUE', label: 'Is True' },
  { value: 'IS_FALSE', label: 'Is False' },
  { value: 'MATCHES_REGEX', label: 'Regex Match' },
];

interface Props {
  clause: ConditionClause;
  onChange: (updated: ConditionClause) => void;
  onRemove: () => void;
  disabled?: boolean;
}

export const ConditionRow: React.FC<Props> = ({
  clause,
  onChange,
  onRemove,
  disabled = false,
}) => {
  const isUnary = clause.operator === 'IS_TRUE' || clause.operator === 'IS_FALSE';

  const handleValueChange = (raw: string) => {
    if (clause.operator === 'IN' || clause.operator === 'NOT_IN') {
      try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          onChange({ ...clause, value: parsed });
          return;
        }
      } catch {
        // Fallback: split by comma if not valid JSON
        const items = raw.split(',').map((s) => s.trim()).filter(Boolean);
        onChange({ ...clause, value: items });
        return;
      }
    } else if (raw === 'true') {
      onChange({ ...clause, value: true });
    } else if (raw === 'false') {
      onChange({ ...clause, value: false });
    } else if (!isNaN(Number(raw)) && raw.trim() !== '') {
      onChange({ ...clause, value: Number(raw) });
    } else {
      onChange({ ...clause, value: raw });
    }
  };

  const displayValue = () => {
    if (isUnary) return '';
    if (Array.isArray(clause.value)) {
      return JSON.stringify(clause.value);
    }
    return clause.value !== undefined && clause.value !== null ? String(clause.value) : '';
  };

  return (
    <div className="flex items-center gap-2 bg-surface p-2 rounded-md border border-border-subtle">
      {/* Attribute */}
      <input
        type="text"
        placeholder="Attribute (e.g. country)"
        value={clause.attribute}
        disabled={disabled}
        onChange={(e) => onChange({ ...clause, attribute: e.target.value })}
        className="w-1/3 bg-surface-elevated text-primary text-xs px-2.5 py-1.5 rounded-sm border border-border-default font-mono focus:border-brand focus-visible:outline-none disabled:opacity-50"
        aria-label="Condition attribute"
      />

      {/* Operator fixed dropdown */}
      <select
        value={clause.operator}
        disabled={disabled}
        onChange={(e) => onChange({ ...clause, operator: e.target.value })}
        className="w-1/3 bg-surface-elevated text-secondary text-xs px-2 py-1.5 rounded-sm border border-border-default focus:border-brand focus-visible:outline-none cursor-pointer disabled:opacity-50"
        aria-label="Condition operator"
      >
        {OPERATORS.map((op) => (
          <option key={op.value} value={op.value}>
            {op.label}
          </option>
        ))}
      </select>

      {/* Value Input */}
      {!isUnary ? (
        <input
          type="text"
          placeholder='Value (e.g. ["VN"])'
          value={displayValue()}
          disabled={disabled}
          onChange={(e) => handleValueChange(e.target.value)}
          className="flex-1 bg-surface-elevated text-primary text-xs px-2.5 py-1.5 rounded-sm border border-border-default font-mono focus:border-brand focus-visible:outline-none disabled:opacity-50"
          aria-label="Condition value"
        />
      ) : (
        <div className="flex-1 text-muted text-[11px] italic px-2">No value needed for boolean check</div>
      )}

      {/* Remove Button */}
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        aria-label="Remove condition clause"
        className="p-1.5 text-muted hover:text-status-danger rounded-sm transition-colors disabled:opacity-40"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
