import React from 'react';
import { Link } from 'react-router-dom';
import { Flag, FlagSetting } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Switch } from '../../components/ui/Switch';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { flagApi } from './api';
import { Copy, Check } from 'lucide-react';

interface Props {
  flag: Flag;
  envId: string;
  envName: string;
}

export const FlagRow: React.FC<Props> = ({ flag, envId, envName }) => {
  const queryClient = useQueryClient();
  const queryKey = ['flag-setting', flag.id, envId];
  const [copied, setCopied] = React.useState(false);

  const { data: setting, isLoading: isSettingLoading } = useQuery({
    queryKey,
    queryFn: () => flagApi.getFlagSetting(flag.id, envId),
    enabled: !!envId,
  });

  const isEnabled = setting?.enabled ?? false;

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

  const copyKey = async () => {
    await navigator.clipboard.writeText(flag.key);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const getTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'BOOLEAN': return 'info';
      case 'JSON': return 'warning';
      case 'NUMBER': return 'default';
      default: return 'outline';
    }
  };

  return (
    <tr className="row-hover group">
      {/* Flag Key & Name */}
      <td className="px-4 py-2.5">
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5">
            <Link
              to={`/flags/${flag.id}`}
              className="font-mono text-xs font-medium text-primary hover:text-brand transition-colors"
            >
              {flag.key}
            </Link>
            <button
              onClick={copyKey}
              className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-muted hover:text-primary rounded-xs"
              aria-label={`Copy flag key ${flag.key}`}
              title="Copy key"
            >
              {copied ? (
                <Check className="w-3 h-3 text-brand" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          </div>
          <span className="text-[11px] text-muted leading-tight line-clamp-1">
            {flag.name}
            {flag.description && ` — ${flag.description}`}
          </span>
        </div>
      </td>

      {/* Type Badge */}
      <td className="px-3 py-2.5">
        <Badge variant={getTypeBadgeVariant(flag.type)} size="sm">
          {flag.type}
        </Badge>
      </td>

      {/* Tags */}
      <td className="px-3 py-2.5">
        <div className="flex flex-wrap gap-1">
          {flag.tags.length > 0 ? (
            flag.tags.slice(0, 3).map((t) => (
              <span
                key={t}
                className="px-1.5 py-px rounded-xs bg-surface-elevated text-muted text-[10px] font-mono border border-border-subtle"
              >
                {t}
              </span>
            ))
          ) : (
            <span className="text-muted/50 text-[10px]">—</span>
          )}
          {flag.tags.length > 3 && (
            <span className="text-[10px] text-muted">+{flag.tags.length - 3}</span>
          )}
        </div>
      </td>

      {/* Toggle */}
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Switch
            checked={isEnabled}
            onChange={(checked) => toggleMutation.mutate(checked)}
            isLoading={isSettingLoading || toggleMutation.isPending}
            disabled={!envId || !!flag.archived_at}
            ariaLabel={`Toggle ${flag.key} in ${envName}`}
            size="sm"
          />
          <span
            className={`text-[10px] font-mono font-medium ${
              isEnabled ? 'text-brand' : 'text-muted'
            }`}
          >
            {isEnabled ? 'ON' : 'OFF'}
          </span>
        </div>
      </td>

      {/* Variations */}
      <td className="px-3 py-2.5 pr-4 text-right">
        <Link
          to={`/flags/${flag.id}`}
          className="text-[11px] text-muted hover:text-primary font-mono transition-colors"
        >
          {flag.variations.length} var{flag.variations.length !== 1 ? 's' : ''}
        </Link>
      </td>
    </tr>
  );
};
