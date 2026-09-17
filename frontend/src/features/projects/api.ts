import { api } from '../../lib/api';
import { Project, Environment } from '../../types';

export const projectApi = {
  listProjects: async (orgId: string): Promise<Project[]> => {
    const res = await api.get<Project[]>(`/api/v1/organizations/${orgId}/projects`);
    return res.data;
  },

  createProject: async (
    orgId: string,
    payload: { key: string; name: string; description?: string }
  ): Promise<Project> => {
    const res = await api.post<Project>(`/api/v1/organizations/${orgId}/projects`, payload);
    return res.data;
  },

  listEnvironments: async (projectId: string): Promise<Environment[]> => {
    const res = await api.get<Environment[]>(`/api/v1/projects/${projectId}/environments`);
    return res.data;
  },

  createEnvironment: async (
    projectId: string,
    payload: { key: string; name: string; description?: string; is_production?: boolean }
  ): Promise<Environment> => {
    const res = await api.post<Environment>(`/api/v1/projects/${projectId}/environments`, payload);
    return res.data;
  },
};
