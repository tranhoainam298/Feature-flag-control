import React from 'react';
import { Flag } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Archive, RotateCcw } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { flagApi } from './api';
import { FlagHealthBadge } from './FlagHealthBadge';

interface Props {
  flag: Flag;
}

export const FlagHeader: React.FC<Props> = ({ flag }) => {
  const queryClient = useQueryClient();
  const isArchived = !!flag.archived_at;

  const { data: health } = useQuery({
    queryKey: ['flag-health', flag.project_id, flag.id],
    queryFn: () => flagApi.getFlagHealth(flag.project_id, flag.id),
    enabled: !!flag.project_id && !!flag.id,
  });

  const archiveMutation = useMutation({
    mutationFn: () => (isArchived ? flagApi.restoreFlag(flag.id) : flagApi.archiveFlag(flag.id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flag', flag.id] });
      queryClient.invalidateQueries({ queryKey: ['flags'] });
      queryClient.invalidateQueries({ queryKey: ['flag-health'] });
    },
  });

  return (
    <div className="border border-border-subtle rounded-md px-4 py-3 bg-surface">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h1 className="text-base font-bold font-mono text-primary tracking-tight">{flag.key}</h1>
            {health && (
              <FlagHealthBadge state={health.state} score={health.score} showScore />
            )}
            <Badge variant="info" size="sm">{flag.type}</Badge>
            {flag.is_temporary && (
              <Badge variant="outline" size="sm">TEMP</Badge>
            )}
            {isArchived && (
              <Badge variant="archived" size="sm">ARCHIVED</Badge>
            )}
          </div>
          <p className="text-xs text-secondary">{flag.name}</p>
          {flag.description && <p className="text-[11px] text-muted mt-0.5">{flag.description}</p>}

          {flag.tags.length > 0 && (
            <div className="flex items-center gap-1 mt-2">
              {flag.tags.map((t) => (
                <span
                  key={t}
                  className="px-1.5 py-px rounded-xs bg-surface-elevated text-muted text-[10px] font-mono border border-border-subtle"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>

        <Button
          variant={isArchived ? 'primary' : 'outline'}
          size="sm"
          onClick={() => archiveMutation.mutate()}
          isLoading={archiveMutation.isPending}
          leftIcon={
            isArchived ? <RotateCcw className="w-3 h-3" /> : <Archive className="w-3 h-3" />
          }
        >
          {isArchived ? 'Restore' : 'Archive'}
        </Button>
      </div>
    </div>
  );
};
