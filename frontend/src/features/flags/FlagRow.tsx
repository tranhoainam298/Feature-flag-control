import React from 'react';
import { Link } from 'react-router-dom';
import { Flag, FlagSetting } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Switch } from '../../components/ui/Switch';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { flagApi } from './api';
import { ChevronRight } from 'lucide-react';

interface Props {
  flag: Flag;
  envId: string;
  envName: string;
}

export const FlagRow: React.FC<Props> = ({ flag, envId, envName }) => {
  const queryClient = useQueryClient();
  const queryKey = ['flag-setting', flag.id, envId];

  // Fetch setting for this flag & environment
  const { data: setting, isLoading: isSettingLoading } = useQuery({
    queryKey,
    queryFn: () => flagApi.getFlagSetting(flag.id, envId),
    enabled: !!envId,
  });

  const isEnabled = setting?.enabled ?? false;

  // Toggle mutation with optimistic update & rollback
  const toggleMutation = useMutation({
    mutationFn: (newEnabled: boolean) =>
      flagApi.updateFlagSetting(flag.id, envId, { enabled: newEnabled }),
    onMutate: async (newEnabled: boolean) => {
      await queryClient.cancelQueries({ queryKey });
      const previousSetting = queryClient.getQueryData<FlagSetting>(queryKey);

      if (previousSetting) {
        queryClient.setQueryData<FlagSetting>(queryKey, {
          ...previousSetting,
          enabled: newEnabled,
        });
      }
      return { previousSetting };
    },
    onError: (_err, _newEnabled, context) => {
      if (context?.previousSetting) {
        queryClient.setQueryData(queryKey, context.previousSetting);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const getTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'BOOLEAN':
        return 'info';
      case 'JSON':
        return 'warning';
      case 'NUMBER':
        return 'default';
      default:
        return 'outline';
    }
  };

  return (
    <tr className="hover:bg-surface-hover/60 transition-colors group">
      {/* Flag Key & Name */}
      <td className="p-3.5 pl-4">
        <div className="flex flex-col">
          <Link
            to={`/flags/${flag.id}`}
            className="font-mono text-xs font-semibold text-primary group-hover:text-brand transition-colors inline-flex items-center gap-1"
          >
            <span>{flag.key}</span>
            <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
          </Link>
          <span className="text-xs text-secondary mt-0.5">{flag.name}</span>
          {flag.description && (
            <span className="text-[11px] text-muted line-clamp-1 mt-0.5">{flag.description}</span>
          )}
        </div>
      </td>

      {/* Flag Type */}
      <td className="p-3.5">
        <Badge variant={getTypeBadgeVariant(flag.type)} size="sm">
          {flag.type}
        </Badge>
      </td>

      {/* Tags */}
      <td className="p-3.5">
        <div className="flex flex-wrap gap-1">
          {flag.tags.length > 0 ? (
            flag.tags.map((t) => (
              <span
                key={t}
                className="px-1.5 py-0.5 rounded-xs bg-surface-elevated text-secondary text-[10px] font-mono border border-border-subtle"
              >
                #{t}
              </span>
            ))
          ) : (
            <span className="text-muted text-[11px]">—</span>
          )}
        </div>
      </td>

      {/* Environment Toggle Switch */}
      <td className="p-3.5">
        <div className="flex items-center gap-2.5">
          <Switch
            checked={isEnabled}
            onChange={(checked) => toggleMutation.mutate(checked)}
            isLoading={isSettingLoading || toggleMutation.isPending}
            disabled={!envId || !!flag.archived_at}
            ariaLabel={`Toggle flag ${flag.key} in ${envName} environment`}
            size="sm"
          />
          <span
            className={`text-[11px] font-mono font-medium ${
              isEnabled ? 'text-flag-on' : 'text-muted'
            }`}
          >
            {isEnabled ? 'ON' : 'OFF'}
          </span>
        </div>
      </td>

      {/* Variations count */}
      <td className="p-3.5 pr-4 text-right">
        <Link
          to={`/flags/${flag.id}`}
          className="text-xs text-secondary hover:text-brand font-medium"
        >
          {flag.variations.length} {flag.variations.length === 1 ? 'var' : 'vars'}
        </Link>
      </td>
    </tr>
  );
};
