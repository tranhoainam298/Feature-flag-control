import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { flagApi } from '../features/flags/api';
import { FlagTable } from '../features/flags/FlagTable';
import { FlagFilterBar } from '../features/flags/FlagFilterBar';
import { CreateFlagModal } from '../features/flags/CreateFlagModal';
import { useApp } from '../context/AppContext';
import { Flag } from '../types';

export const FlagsPage: React.FC = () => {
  const { currentProject, currentEnvironment } = useApp();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const projectId = currentProject?.id || '';
  const envId = currentEnvironment?.id || '';

  const {
    data: flags,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['flags', projectId, search, typeFilter, showArchived],
    queryFn: () =>
      flagApi.listFlags(projectId, {
        search: search.trim() || undefined,
        type: typeFilter || undefined,
        archived: showArchived ? true : false,
      }),
    enabled: !!projectId,
  });

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-primary">Feature Flags</h1>
          <p className="text-[11px] text-muted mt-0.5">
            Runtime flag management for{' '}
            <span className="text-secondary font-medium">{currentProject?.name || 'Project'}</span>
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <FlagFilterBar
        search={search}
        onSearchChange={setSearch}
        typeFilter={typeFilter}
        onTypeFilterChange={setTypeFilter}
        showArchived={showArchived}
        onToggleArchived={() => setShowArchived((prev) => !prev)}
        onOpenCreate={() => setIsCreateOpen(true)}
      />

      {/* Data Table */}
      <FlagTable
        flags={flags as Flag[]}
        isLoading={isLoading}
        isError={isError}
        error={error}
        envId={envId}
        envName={currentEnvironment?.name}
        onRetry={() => refetch()}
        onOpenCreate={() => setIsCreateOpen(true)}
      />

      {/* Create Modal */}
      {projectId && (
        <CreateFlagModal
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          projectId={projectId}
        />
      )}
    </div>
  );
};
