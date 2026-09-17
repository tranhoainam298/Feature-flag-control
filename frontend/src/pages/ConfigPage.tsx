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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
            Trung tâm Cấu hình (Config Center)
          </h1>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Quản lý cấu hình runtime, biến môi trường có versioning, diff, rollback và mã hóa bí mật theo từng Namespace.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Tạo Namespace mới</span>
        </button>
      </div>

      {/* Environment selector bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-[var(--surface)] p-3 rounded-xl border border-[var(--border)]">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" />
          <span className="text-xs font-semibold text-[var(--text-primary)]">
            Môi trường:
          </span>
          <div className="flex items-center gap-1 bg-[var(--surface-sunken)] p-1 rounded-lg border border-[var(--border)]">
            {environments.map((env) => (
              <button
                key={env.id}
                type="button"
                onClick={() => setSelectedEnvId(env.id)}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-all cursor-pointer ${
                  activeEnvId === env.id
                    ? 'bg-indigo-600 text-white shadow-xs font-semibold'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                {env.name}
              </button>
            ))}
          </div>
        </div>

        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[var(--text-tertiary)]" />
          <input
            type="text"
            placeholder="Tìm kiếm namespace..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] pl-9 pr-3 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-tertiary)] focus:border-indigo-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <SkeletonTable rows={4} columns={3} />
      ) : isError ? (
        <ErrorAlert error={error || 'Lỗi tải danh sách namespace'} onRetry={() => refetch()} />
      ) : filteredNamespaces.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-400 mb-3">
            <Database className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            {searchTerm ? 'Không tìm thấy namespace phù hợp' : `Chưa có namespace nào tại ${activeEnv?.name}`}
          </h3>
          <p className="mt-1 text-xs text-[var(--text-tertiary)] max-w-sm mx-auto">
            Tạo namespace đầu tiên để lưu trữ cấu hình key-value và bí mật cho ứng dụng của bạn.
          </p>
          {!searchTerm && (
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Tạo Namespace đầu tiên</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
