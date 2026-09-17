import React from 'react';
import { Flag } from '../../types';
import { FlagRow } from './FlagRow';
import { SkeletonTable } from '../../components/ui/SkeletonTable';
import { ErrorAlert } from '../../components/ui/ErrorAlert';
import { EmptyState } from '../../components/ui/EmptyState';
import { Flag as FlagIcon, Plus } from 'lucide-react';
import { Button } from '../../components/ui/Button';

interface Props {
  flags?: Flag[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  envId?: string;
  envName?: string;
  onRetry: () => void;
  onOpenCreate: () => void;
}

export const FlagTable: React.FC<Props> = ({
  flags,
  isLoading,
  isError,
  error,
  envId,
  envName,
  onRetry,
  onOpenCreate,
}) => {
  if (isLoading) {
    return <SkeletonTable rows={8} columns={5} />;
  }

  if (isError) {
    return <ErrorAlert error={error} onRetry={onRetry} title="Failed to load flags" />;
  }

  if (!flags || flags.length === 0) {
    return (
      <EmptyState
        icon={<FlagIcon className="w-5 h-5" />}
        title="No feature flags"
        description="Create your first flag to start managing feature rollouts."
        action={
          <Button
            variant="primary"
            size="sm"
            onClick={onOpenCreate}
            leftIcon={<Plus className="w-3.5 h-3.5" />}
          >
            Create Flag
          </Button>
        }
      />
    );
  }

  return (
    <div className="border border-border-subtle rounded-md overflow-hidden bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="bg-surface-elevated border-b border-border-subtle">
            <tr className="text-[10px] font-mono text-muted uppercase tracking-wider">
              <th className="px-4 py-2 font-medium">Flag Key</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Tags</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium text-right pr-4">Variations</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {flags.map((flag) => (
              <FlagRow
                key={flag.id}
                flag={flag}
                envId={envId || ''}
                envName={envName || 'Environment'}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
