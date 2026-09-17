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
    return <SkeletonTable rows={5} columns={5} />;
  }

  if (isError) {
    return <ErrorAlert error={error} onRetry={onRetry} title="Failed to load flags" />;
  }

  if (!flags || flags.length === 0) {
    return (
      <EmptyState
        icon={<FlagIcon className="w-6 h-6" />}
        title="No feature flags found"
        description="Get started by creating your first flag or adjust your search filter."
        action={
          <Button
            variant="primary"
            size="sm"
            onClick={onOpenCreate}
            leftIcon={<Plus className="w-4 h-4" />}
          >
            Create Feature Flag
          </Button>
        }
      />
    );
  }

  return (
    <div className="border border-border-default rounded-lg overflow-hidden bg-surface shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="bg-surface-elevated border-b border-border-subtle text-muted uppercase font-mono text-[10px] tracking-wider">
            <tr>
              <th className="p-3.5 pl-4">Feature Flag</th>
              <th className="p-3.5">Type</th>
              <th className="p-3.5">Tags</th>
              <th className="p-3.5">Status ({envName || 'Environment'})</th>
              <th className="p-3.5 pr-4 text-right">Variations</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle text-secondary">
            {flags.map((flag) => (
              <FlagRow
                key={flag.id}
                flag={flag}
                envId={envId || ''}
                envName={envName || 'Selected Environment'}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
