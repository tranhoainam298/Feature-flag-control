import React from 'react';
import { TargetingRuleInput, Variation, ConditionGroupData } from '../../types';
import { ConditionGroup } from '../../components/conditions/ConditionGroup';
import { DistributionEditor } from './DistributionEditor';
import { ChevronUp, ChevronDown, Trash2 } from 'lucide-react';

interface RuleCardProps {
  rule: TargetingRuleInput;
  index: number;
  totalRules: number;
  variations: Variation[];
  onUpdate: (updated: TargetingRuleInput) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDelete: () => void;
  disabled?: boolean;
}

export const RuleCard: React.FC<RuleCardProps> = ({
  rule,
  index,
  totalRules,
  variations,
  onUpdate,
  onMoveUp,
  onMoveDown,
  onDelete,
  disabled = false,
}) => {
  // Ensure conditions object is normalized to ConditionGroupData
  const groupData: ConditionGroupData =
    rule.conditions && typeof rule.conditions === 'object' && 'operator' in rule.conditions
      ? (rule.conditions as ConditionGroupData)
      : { operator: 'AND', conditions: [] };

  return (
    <div className="rounded-md border border-border-default bg-surface p-3.5 shadow-xs space-y-3">
      {/* Header: Priority & Move controls */}
      <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded-xs bg-brand/10 text-[11px] font-bold font-mono text-brand border border-brand/20">
            #{rule.priority}
          </span>
          <span className="text-xs font-semibold text-primary">
            Rule Priority #{rule.priority}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            title="Move up (increase priority)"
            disabled={disabled || index === 0}
            onClick={onMoveUp}
            className="flex h-6 w-6 items-center justify-center rounded-xs border border-border-default bg-surface-elevated text-secondary hover:text-primary hover:bg-surface-elevated/80 disabled:opacity-40 disabled:pointer-events-none transition-colors"
            aria-label="Move rule up"
          >
            <ChevronUp className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            title="Move down (decrease priority)"
            disabled={disabled || index === totalRules - 1}
            onClick={onMoveDown}
            className="flex h-6 w-6 items-center justify-center rounded-xs border border-border-default bg-surface-elevated text-secondary hover:text-primary hover:bg-surface-elevated/80 disabled:opacity-40 disabled:pointer-events-none transition-colors"
            aria-label="Move rule down"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            title="Delete rule"
            disabled={disabled}
            onClick={onDelete}
            className="flex h-6 w-6 items-center justify-center rounded-xs border border-status-danger/30 bg-status-danger/10 text-status-danger hover:bg-status-danger/20 disabled:opacity-40 transition-colors ml-1"
            aria-label="Delete rule"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Description */}
      <div>
        <label className="block text-[11px] font-medium text-secondary mb-1">
          Description (optional)
        </label>
        <input
          type="text"
          value={rule.description || ''}
          placeholder="e.g. VIP customers in APAC region, early access users"
          disabled={disabled}
          onChange={(e) => onUpdate({ ...rule, description: e.target.value })}
          className="w-full rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1.5 text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
        />
      </div>

      {/* Condition Group */}
      <div>
        <div className="mb-1 text-[11px] font-medium text-secondary">
          Targeting Match Conditions
        </div>
        <ConditionGroup
          group={groupData}
          onChange={(newGroup) => onUpdate({ ...rule, conditions: newGroup })}
          disabled={disabled}
        />
      </div>

      {/* Distribution Rollout */}
      <DistributionEditor
        variations={variations}
        distribution={rule.distribution}
        onChange={(dist) => onUpdate({ ...rule, distribution: dist })}
        disabled={disabled}
      />
    </div>
  );
};
