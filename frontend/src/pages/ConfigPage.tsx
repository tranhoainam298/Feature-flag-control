import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { configApi } from '../features/config/api';
import { NamespaceCard } from '../features/config/NamespaceCard';
import { CreateNamespaceModal } from '../features/config/CreateNamespaceModal';
import { useApp } from '../context/AppContext';
import { Database, Plus, Search, Layers } from 'lucide-react';
import { SkeletonTable } from '../components/ui/SkeletonTable';
import { ErrorAlert } from '../components/ui/ErrorAlert';

export const ConfigPage: React.FC = () => {
  const { environments, currentEnvironment } = useApp();
  const [selectedEnvId, setSelectedEnvId] = useState<string>(
    currentEnvironment?.id || environments[0]?.id || ''
  );
  const [searchTerm, setSearchTerm] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const activeEnvId = selectedEnvId || currentEnvironment?.id || environments[0]?.id || '';
  const activeEnv = environments.find((e) => e.id === activeEnvId) || currentEnvironment;

  const {
    data: namespaces = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['config-namespaces', activeEnvId],
    queryFn: () => configApi.listNamespaces(activeEnvId),
    enabled: !!activeEnvId,
  });

  const filteredNamespaces = namespaces.filter((ns) =>
    ns.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-default pb-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-primary">
            Configuration Center
          </h1>
          <p className="mt-0.5 text-xs text-secondary">
            Centralized runtime configurations, environment variables, secret encryption, and versioned releases per namespace.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-xs bg-brand px-3 py-1.5 text-xs font-medium text-white shadow-xs hover:bg-brand-hover transition-colors cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Create Namespace</span>
        </button>
      </div>

      {/* Environment selector bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-surface p-2.5 rounded-md border border-border-default">
        <div className="flex items-center gap-2">
          <Layers className="w-3.5 h-3.5 text-secondary" />
          <span className="text-xs font-medium text-secondary">
            Environment:
          </span>
          <div className="flex items-center gap-1 bg-surface-elevated p-0.5 rounded-xs border border-border-default">
            {environments.map((env) => (
              <button
                key={env.id}
                type="button"
                onClick={() => setSelectedEnvId(env.id)}
                className={`px-2.5 py-1 text-xs font-medium rounded-xs transition-colors cursor-pointer ${
                  activeEnvId === env.id
                    ? 'bg-brand text-white font-semibold shadow-xs'
                    : 'text-secondary hover:text-primary'
                }`}
              >
                {env.name}
              </button>
            ))}
          </div>
        </div>

        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted" />
          <input
            type="text"
            placeholder="Search namespaces..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-xs border border-border-default bg-surface-elevated pl-8 pr-3 py-1.5 text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
          />
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <SkeletonTable rows={4} columns={3} />
      ) : isError ? (
        <ErrorAlert error={error || 'Failed to load configuration namespaces'} onRetry={() => refetch()} />
      ) : filteredNamespaces.length === 0 ? (
        <div className="rounded-md border border-dashed border-border-default p-10 text-center bg-surface/50">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xs bg-brand/10 text-brand border border-brand/20 mb-2.5">
            <Database className="w-5 h-5" />
          </div>
          <h3 className="text-xs font-semibold text-primary">
            {searchTerm ? 'No matching namespaces found' : `No namespaces in ${activeEnv?.name || 'environment'}`}
          </h3>
          <p className="mt-1 text-xs text-muted max-w-sm mx-auto">
            Create a namespace to organize key-value configurations, application variables, and encrypted secrets.
          </p>
          {!searchTerm && (
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="mt-3.5 inline-flex items-center gap-1.5 rounded-xs bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-hover transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create First Namespace</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filteredNamespaces.map((ns) => (
            <NamespaceCard key={ns.id} namespace={ns} />
          ))}
        </div>
      )}

      {/* Create Modal */}
      {isCreateOpen && (
        <CreateNamespaceModal
          envId={activeEnvId}
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
        />
      )}
    </div>
  );
};
