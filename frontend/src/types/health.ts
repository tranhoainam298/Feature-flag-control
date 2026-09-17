export type LifecycleState = 'DRAFT' | 'ACTIVE' | 'ROLLED_OUT' | 'STALE' | 'ARCHIVED';

export interface FlagHealthItem {
  flag_id: string;
  flag_key: string;
  flag_name: string;
  state: LifecycleState;
  score: number;
  age_score: number;
  rollout_score: number;
  staleness_score: number;
  temporary_score: number;
  recommendations: string[];
  is_temporary: boolean;
  tags: string[];
}

export interface FlagHealthSummary {
  total: number;
  draft_count: number;
  active_count: number;
  rolled_out_count: number;
  stale_count: number;
  archived_count: number;
  avg_score: number;
}

export interface FlagHealthListResponse {
  items: FlagHealthItem[];
  summary: FlagHealthSummary;
}
