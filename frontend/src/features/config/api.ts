import { api } from '../../lib/api';
import {
  ConfigNamespace,
  ConfigItem,
  ConfigItemInput,
  ConfigDiffResponse,
  ConfigRelease,
} from '../../types';

export const configApi = {
  listNamespaces: async (envId: string): Promise<ConfigNamespace[]> => {
    const res = await api.get<ConfigNamespace[]>(`/api/v1/environments/${envId}/namespaces`);
    return res.data;
  },

  createNamespace: async (
    envId: string,
    payload: { name: string; format?: 'json' | 'yaml' | 'properties' }
  ): Promise<ConfigNamespace> => {
    const res = await api.post<ConfigNamespace>(
      `/api/v1/environments/${envId}/namespaces`,
      payload
    );
    return res.data;
  },

  listDraftItems: async (namespaceId: string, reveal: boolean = false): Promise<ConfigItem[]> => {
    const res = await api.get<ConfigItem[]>(`/api/v1/namespaces/${namespaceId}/items`, {
      params: { reveal },
    });
    return res.data;
  },

  updateDraftItems: async (
    namespaceId: string,
    items: ConfigItemInput[]
  ): Promise<ConfigItem[]> => {
    const res = await api.put<ConfigItem[]>(`/api/v1/namespaces/${namespaceId}/items`, { items });
    return res.data;
  },

  getPendingDiff: async (namespaceId: string): Promise<ConfigDiffResponse> => {
    const res = await api.get<ConfigDiffResponse>(
      `/api/v1/namespaces/${namespaceId}/pending-diff`
    );
    return res.data;
  },

  publishRelease: async (
    namespaceId: string,
    comment: string
  ): Promise<ConfigRelease> => {
    const res = await api.post<ConfigRelease>(
      `/api/v1/namespaces/${namespaceId}/releases`,
      { comment }
    );
    return res.data;
  },

  listReleases: async (namespaceId: string): Promise<ConfigRelease[]> => {
    const res = await api.get<ConfigRelease[]>(`/api/v1/namespaces/${namespaceId}/releases`);
    return res.data;
  },

  getReleasesDiff: async (
    namespaceId: string,
    v1: number,
    v2: number
  ): Promise<ConfigDiffResponse> => {
    const res = await api.get<ConfigDiffResponse>(
      `/api/v1/namespaces/${namespaceId}/releases/${v1}/diff/${v2}`
    );
    return res.data;
  },

  rollbackRelease: async (
    namespaceId: string,
    version: number
  ): Promise<ConfigRelease> => {
    const res = await api.post<ConfigRelease>(
      `/api/v1/namespaces/${namespaceId}/releases/${version}/rollback`
    );
    return res.data;
  },
};
