export interface RuleTraceItem {
  rule_id: string | null;
  priority: number | null;
  description: string | null;
  matched: boolean;
  reason: string;
}

export interface SimulateRequest {
  context: Record<string, unknown>;
}

export interface SimulateResponse {
  flag_key: string;
  value: unknown;
  variant: string;
  reason: string;
  matched_rule_id: string | null;
  matched_rule_description: string | null;
  trace: RuleTraceItem[];
}
