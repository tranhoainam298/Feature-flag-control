export type ChangeRequestStatus =
  | 'DRAFT'
  | 'PENDING'
  | 'APPROVED'
  | 'APPLIED'
  | 'REJECTED'
  | 'CANCELLED';

export interface ChangeRequest {
  id: string;
  environment_id: string;
  title: string;
  description: string | null;
  payload: Record<string, any>;
  status: ChangeRequestStatus;
  requested_by: string;
  reviewed_by: string | null;
  scheduled_at: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImpactTransition {
  from_variation: string;
  to_variation: string;
  count: number;
}

export interface ChangeRequestImpact {
  total_contexts: number;
  affected_contexts: number;
  change_percentage: number;
  transitions: ImpactTransition[];
  summary: string;
  flag_key: string | null;
}
