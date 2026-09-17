import { api } from '../../lib/api';
import {
  Flag,
  FlagSetting,
  FlagCreatePayload,
  FlagSettingUpdatePayload,
  SimulateResponse,
} from '../../types';

export interface ListFlagsParams {
  tag?: string;
  type?: string;
  archived?: boolean;
  search?: string;
}

export const flagApi = {
  listFlags: async (projectId: string, params?: ListFlagsParams): Promise<Flag[]> => {
    const res = await api.get<Flag[]>(`/api/v1/projects/${projectId}/flags`, { params });
    return res.data;
  },

  createFlag: async (projectId: string, payload: FlagCreatePayload): Promise<Flag> => {
    const res = await api.post<Flag>(`/api/v1/projects/${projectId}/flags`, payload);
    return res.data;
  },

  getFlag: async (flagId: string): Promise<Flag> => {
    const res = await api.get<Flag>(`/api/v1/flags/${flagId}`);
    return res.data;
  },

  archiveFlag: async (flagId: string): Promise<Flag> => {
    const res = await api.post<Flag>(`/api/v1/flags/${flagId}/archive`);
    return res.data;
  },

  restoreFlag: async (flagId: string): Promise<Flag> => {
    const res = await api.post<Flag>(`/api/v1/flags/${flagId}/restore`);
    return res.data;
  },

  getFlagSetting: async (flagId: string, envId: string): Promise<FlagSetting> => {
    const res = await api.get<FlagSetting>(`/api/v1/flags/${flagId}/environments/${envId}`);
    return res.data;
  },

  updateFlagSetting: async (
    flagId: string,
    envId: string,
    payload: FlagSettingUpdatePayload
  ): Promise<FlagSetting> => {
    const res = await api.put<FlagSetting>(
      `/api/v1/flags/${flagId}/environments/${envId}`,
      payload
    );
    return res.data;
  },

  simulateEvaluation: async (
    flagId: string,
    envId: string,
    context: Record<string, unknown>
  ): Promise<SimulateResponse> => {
    const res = await api.post<SimulateResponse>(
      `/api/v1/flags/${flagId}/environments/${envId}/simulate`,
      { context }
    );
    return res.data;
  },

  listFlagHealth: async (
    projectId: string,
    params?: { state?: string; min_score?: number; sort?: string }
  ): Promise<import('../../types').FlagHealthListResponse> => {
    const res = await api.get<import('../../types').FlagHealthListResponse>(
      `/api/v1/projects/${projectId}/flag-health`,
      { params }
    );
    return res.data;
  },

  getFlagHealth: async (
    projectId: string,
    flagId: string
  ): Promise<import('../../types').FlagHealthItem> => {
    const res = await api.get<import('../../types').FlagHealthItem>(
      `/api/v1/projects/${projectId}/flags/${flagId}/health`
    );
    return res.data;
  },

  archiveFlagByHealth: async (
    projectId: string,
    flagId: string
  ): Promise<import('../../types').FlagHealthItem> => {
    const res = await api.post<import('../../types').FlagHealthItem>(
      `/api/v1/projects/${projectId}/flags/${flagId}/archive`
    );
    return res.data;
  },
};

