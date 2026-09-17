export interface DistributionItem {
  variation_id: string;
  weight: number;
}

export interface ConditionClause {
  attribute: string;
  operator: string;
  value: unknown;
}

export interface ConditionGroupData {
  operator: 'AND' | 'OR';
  conditions: Array<ConditionClause | ConditionGroupData>;
}

export interface TargetingRule {
  id: string;
  flag_environment_setting_id: string;
  priority: number;
  description: string | null;
  segment_id: string | null;
  conditions: ConditionGroupData | ConditionClause | null;
  distribution: DistributionItem[];
  created_at: string;
  updated_at: string;
}

export interface TargetingRuleInput {
  priority: number;
  description?: string | null;
  segment_id?: string | null;
  conditions?: ConditionGroupData | ConditionClause | null;
  distribution: DistributionItem[];
}
