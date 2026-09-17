import { api } from '../../lib/api';
import { AuditLogItem } from '../../types';

export interface AuditLogFilters {
  projectId?: string;
  environmentId?: string;
  action?: string;
  entityType?: string;
  limit?: number;
  cursor?: number;
}

export const auditApi = {
  listAuditLogs: async (filters?: AuditLogFilters): Promise<AuditLogItem[]> => {
    const params: Record<string, unknown> = {};
    if (filters?.projectId) params.project_id = filters.projectId;
    if (filters?.environmentId) params.environment_id = filters.environmentId;
    if (filters?.action) params.action = filters.action;
    if (filters?.entityType && filters.entityType !== 'ALL') params.entity_type = filters.entityType;
    if (filters?.limit) params.limit = filters.limit;
    if (filters?.cursor) params.cursor = filters.cursor;

    const res = await api.get<AuditLogItem[]>('/api/v1/audit', { params });
    return res.data;
  },
};
