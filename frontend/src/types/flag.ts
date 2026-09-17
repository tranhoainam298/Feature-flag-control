export type FlagType = 'BOOLEAN' | 'STRING' | 'NUMBER' | 'JSON';
export type ToggleKind = 'RELEASE' | 'EXPERIMENT' | 'OPERATIONAL' | 'PERMISSION';

export interface Variation {
  id: string;
  flag_id: string;
  key: string;
  value: unknown;
  description: string | null;
  created_at?: string;
}

export interface Flag {
  id: string;
  project_id: string;
  key: string;
  name: string;
  description: string | null;
  type: FlagType;
  toggle_kind: ToggleKind;
  is_temporary: boolean;
  is_client_visible: boolean;
  tags: string[];
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  variations: Variation[];
}

export interface FlagSetting {
  id: string;
  flag_id: string;
  environment_id: string;
  enabled: boolean;
  default_variation_id: string | null;
  off_variation_id: string | null;
  bucketing_key: string;
  last_evaluated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FlagCreatePayload {
  key: string;
  name: string;
  description?: string | null;
  type: FlagType;
  toggle_kind?: ToggleKind;
  is_temporary?: boolean;
  is_client_visible?: boolean;
  tags?: string[];
  variations?: Array<{
    key: string;
    value: unknown;
    description?: string | null;
  }>;
}

export interface FlagSettingUpdatePayload {
  enabled?: boolean;
  default_variation_id?: string | null;
  off_variation_id?: string | null;
  bucketing_key?: string | null;
}
