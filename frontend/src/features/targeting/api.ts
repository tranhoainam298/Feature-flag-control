import { api } from '../../lib/api';
import { TargetingRule, TargetingRuleInput } from '../../types';

export const targetingApi = {
  listTargetingRules: async (flagId: string, envId: string): Promise<TargetingRule[]> => {
    const res = await api.get<TargetingRule[]>(
      `/api/v1/flags/${flagId}/environments/${envId}/rules`
    );
    return res.data;
  },

  updateTargetingRules: async (
    flagId: string,
    envId: string,
    rules: TargetingRuleInput[]
  ): Promise<TargetingRule[]> => {
    const res = await api.put<TargetingRule[]>(
      `/api/v1/flags/${flagId}/environments/${envId}/rules`,
      { rules }
    );
    return res.data;
  },
};
