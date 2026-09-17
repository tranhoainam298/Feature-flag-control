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
    <div className="border border-border-default rounded-lg p-6 bg-surface mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <h1 className="text-xl font-bold font-mono text-primary tracking-tight">{flag.key}</h1>
            {health && (
              <FlagHealthBadge state={health.state} score={health.score} showScore />
            )}
            <Badge variant="info" size="sm">
              {flag.type}
            </Badge>
            {flag.is_temporary && (
              <Badge variant="outline" size="sm">
                TEMPORARY
              </Badge>
            )}
            {isArchived && (
              <Badge variant="danger" size="sm">
                ARCHIVED
              </Badge>
            )}
          </div>
          <p className="text-sm font-medium text-secondary">{flag.name}</p>
          {flag.description && <p className="text-xs text-muted mt-1">{flag.description}</p>}

          {/* Tags */}
          {flag.tags.length > 0 && (
            <div className="flex items-center gap-1.5 mt-3">
              {flag.tags.map((t) => (
                <span
                  key={t}
                  className="px-2 py-0.5 rounded-xs bg-surface-elevated text-secondary text-[11px] font-mono border border-border-subtle"
                >
                  #{t}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={isArchived ? 'primary' : 'outline'}
            size="sm"
            onClick={() => archiveMutation.mutate()}
            isLoading={archiveMutation.isPending}
            leftIcon={
              isArchived ? <RotateCcw className="w-3.5 h-3.5" /> : <Archive className="w-3.5 h-3.5" />
            }
          >
            {isArchived ? 'Restore Flag' : 'Archive Flag'}
          </Button>
        </div>
      </div>
    </div>
  );
};
