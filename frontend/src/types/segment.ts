import { ConditionGroupData } from './targeting';

export interface Segment {
  id: string;
  project_id: string;
  key: string;
  name: string;
  description: string | null;
  conditions: ConditionGroupData;
  created_at: string;
  updated_at: string;
}

export interface SegmentCreatePayload {
  key: string;
  name: string;
  description?: string | null;
  conditions: ConditionGroupData;
}
