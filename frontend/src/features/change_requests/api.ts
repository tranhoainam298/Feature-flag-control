import { api } from '../../lib/api';
import { ChangeRequest, ChangeRequestImpact, ChangeRequestStatus } from '../../types';

export const changeRequestApi = {
  listChangeRequests: async (envId: string, status?: ChangeRequestStatus): Promise<ChangeRequest[]> => {
    const params: Record<string, string> = {};
    if (status) params.status = status;
    const res = await api.get<ChangeRequest[]>(`/api/v1/environments/${envId}/change-requests`, { params });
    return res.data;
  },

  getChangeRequest: async (id: string): Promise<ChangeRequest> => {
    const res = await api.get<ChangeRequest>(`/api/v1/change-requests/${id}`);
    return res.data;
  },

  getImpact: async (id: string): Promise<ChangeRequestImpact> => {
    const res = await api.get<ChangeRequestImpact>(`/api/v1/change-requests/${id}/impact`);
    return res.data;
  },

  approve: async (id: string): Promise<ChangeRequest> => {
    const res = await api.post<ChangeRequest>(`/api/v1/change-requests/${id}/approve`);
    return res.data;
  },

  reject: async (id: string): Promise<ChangeRequest> => {
    const res = await api.post<ChangeRequest>(`/api/v1/change-requests/${id}/reject`);
    return res.data;
  },

  cancel: async (id: string): Promise<ChangeRequest> => {
    const res = await api.post<ChangeRequest>(`/api/v1/change-requests/${id}/cancel`);
    return res.data;
  },
};
