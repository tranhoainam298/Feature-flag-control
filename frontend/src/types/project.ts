export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  organization_id: string;
  key: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Environment {
  id: string;
  project_id: string;
  key: string;
  name: string;
  description: string | null;
  is_production: boolean;
  ruleset_version: number;
  created_at: string;
  updated_at: string;
}
