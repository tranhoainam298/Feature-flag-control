export type ConfigFormat = 'json' | 'yaml' | 'properties';
export type ConfigValueType = 'string' | 'number' | 'boolean' | 'json';

export interface ConfigNamespace {
  id: string;
  environment_id: string;
  name: string;
  format: ConfigFormat;
  current_release_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConfigItem {
  id: string;
  namespace_id: string;
  key: string;
  value: string;
  value_type: ConfigValueType;
  is_secret: boolean;
  json_schema: Record<string, unknown> | null;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConfigItemInput {
  key: string;
  value: string;
  value_type: ConfigValueType;
  is_secret?: boolean;
  json_schema?: Record<string, unknown> | null;
  comment?: string | null;
}

export interface ConfigDiffResponse {
  added: Record<string, unknown>;
  removed: Record<string, unknown>;
  changed: Record<string, { old: unknown; new: unknown }>;
  unchanged: Record<string, unknown>;
}

export interface ConfigRelease {
  id: string;
  namespace_id: string;
  version: number;
  snapshot: Record<string, unknown>;
  comment: string | null;
  released_by: string | null;
  released_at: string;
  is_rollback_of: string | null;
}
