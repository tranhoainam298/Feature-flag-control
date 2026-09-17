import React from 'react';
import { ConditionClause, ConditionGroupData } from '../../types';
import { ConditionRow } from './ConditionRow';
import { Plus } from 'lucide-react';
import { Button } from '../ui/Button';

interface Props {
  group: ConditionGroupData;
  onChange: (updated: ConditionGroupData) => void;
  disabled?: boolean;
}

export const ConditionGroup: React.FC<Props> = ({
  group,
  onChange,
  disabled = false,
}) => {
  const handleCombinatorChange = (op: 'AND' | 'OR') => {
    onChange({ ...group, operator: op });
  };

  const handleClauseChange = (index: number, updatedClause: ConditionClause) => {
    const updatedConditions = [...group.conditions];
    updatedConditions[index] = updatedClause;
    onChange({ ...group, conditions: updatedConditions });
  };

  const handleRemoveClause = (index: number) => {
    const updatedConditions = group.conditions.filter((_, i) => i !== index);
    onChange({ ...group, conditions: updatedConditions });
  };

  const handleAddClause = () => {
    const newClause: ConditionClause = { attribute: '', operator: 'EQ', value: '' };
    onChange({ ...group, conditions: [...group.conditions, newClause] });
  };

  return (
    <div className="bg-surface-elevated/40 border border-border-subtle rounded-md p-3 space-y-3">
      {/* Header with AND/OR Switcher */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-secondary uppercase tracking-wider">
            Match Clauses:
          </span>
          <div className="inline-flex rounded-sm border border-border-default bg-surface p-0.5">
            <button
              type="button"
              onClick={() => handleCombinatorChange('AND')}
              className={`px-2 py-0.5 text-xs font-mono rounded-xs transition-colors ${
                group.operator === 'AND'
                  ? 'bg-brand text-white font-bold'
                  : 'text-muted hover:text-primary'
              }`}
            >
              ALL (AND)
            </button>
            <button
              type="button"
              onClick={() => handleCombinatorChange('OR')}
              className={`px-2 py-0.5 text-xs font-mono rounded-xs transition-colors ${
                group.operator === 'OR'
                  ? 'bg-brand text-white font-bold'
                  : 'text-muted hover:text-primary'
              }`}
            >
              ANY (OR)
            </button>
          </div>
        </div>

        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={handleAddClause}
          disabled={disabled}
          leftIcon={<Plus className="w-3 h-3" />}
          className="h-6 text-[11px] px-2"
        >
          Add Clause
        </Button>
      </div>

      {/* Clauses list */}
      <div className="space-y-2">
        {group.conditions.length === 0 ? (
          <div className="text-center py-3 text-xs text-muted border border-dashed border-border-subtle rounded-sm">
            No conditions specified. Click &quot;Add Clause&quot; to target specific users.
          </div>
        ) : (
          group.conditions.map((item, idx) => {
            // Support simple ConditionClause
            const clause = item as ConditionClause;
            return (
              <ConditionRow
                key={idx}
                clause={clause}
                onChange={(updated) => handleClauseChange(idx, updated)}
                onRemove={() => handleRemoveClause(idx)}
                disabled={disabled}
              />
            );
          })
        )}
      </div>
    </div>
  );
};
