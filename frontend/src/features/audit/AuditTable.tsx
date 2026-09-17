import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { auditApi } from './api';
import { AuditLogItem } from '../../types';
import { AuditDetailModal } from './AuditDetailModal';
import { Search, Filter, ShieldAlert, ChevronRight, RefreshCw } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { SkeletonTable } from '../../components/ui/SkeletonTable';

export const AuditTable: React.FC = () => {
  const { currentProject } = useApp();
  const [actionQuery, setActionQuery] = useState('');
  const [entityType, setEntityType] = useState('ALL');
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);
  const [cursor, setCursor] = useState<number | undefined>(undefined);
  const [historyStack, setHistoryStack] = useState<number[]>([]);

  const {
    data: logs = [],
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['audit-logs', currentProject?.id, actionQuery, entityType, cursor],
    queryFn: () =>
      auditApi.listAuditLogs({
        projectId: currentProject?.id,
        action: actionQuery || undefined,
        entityType: entityType !== 'ALL' ? entityType : undefined,
        limit: 25,
        cursor,
      }),
    enabled: Boolean(currentProject?.id),
  });

  const handleNextPage = () => {
    if (logs.length > 0) {
      const minId = Math.min(...logs.map((l) => l.id));
      setHistoryStack([...historyStack, cursor || 0]);
      setCursor(minId);
    }
  };

  const handleResetPagination = () => {
    setCursor(undefined);
    setHistoryStack([]);
  };

  const getActionBadgeColor = (action: string) => {
    if (action.includes('created') || action.includes('publish')) {
      return 'bg-status-success/10 text-status-success border-status-success/30';
    }
    if (action.includes('updated') || action.includes('toggle')) {
      return 'bg-status-warning/10 text-status-warning border-status-warning/30';
    }
    if (action.includes('deleted') || action.includes('rollback')) {
      return 'bg-status-danger/10 text-status-danger border-status-danger/30';
    }
    return 'bg-brand/10 text-brand border-brand/30';
  };

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-surface p-2.5 rounded-md border border-border-default">
        <div className="flex flex-wrap items-center gap-2 flex-1">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted" />
            <input
              type="text"
              placeholder="Filter by action (e.g. flag, config, release)..."
              value={actionQuery}
              onChange={(e) => {
                setActionQuery(e.target.value);
                handleResetPagination();
              }}
              className="w-full rounded-xs border border-border-default bg-surface-elevated pl-8 pr-3 py-1.5 text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-muted" />
            <select
              value={entityType}
              onChange={(e) => {
                setEntityType(e.target.value);
                handleResetPagination();
              }}
              className="rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1.5 text-xs text-primary focus:outline-none focus:border-brand"
            >
              <option value="ALL">All Entity Types</option>
              <option value="flag">flag</option>
              <option value="flag_variation">flag_variation</option>
              <option value="flag_environment_setting">flag_environment_setting</option>
              <option value="targeting_rule">targeting_rule</option>
              <option value="segment">segment</option>
              <option value="config_namespace">config_namespace</option>
              <option value="config_release">config_release</option>
              <option value="api_key">api_key</option>
              <option value="auth">auth</option>
            </select>
          </div>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="rounded-xs border border-border-default bg-surface-elevated p-1.5 text-secondary hover:text-primary transition-colors cursor-pointer"
          title="Refresh audit records"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Table */}
      {isLoading ? (
        <SkeletonTable rows={8} columns={5} />
      ) : isError ? (
        <div className="rounded-md border border-status-danger/30 bg-status-danger/10 p-3 text-xs text-status-danger">
          Failed to load audit records.
        </div>
      ) : logs.length === 0 ? (
        <div className="rounded-md border border-dashed border-border-default p-10 text-center bg-surface/50">
          <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-xs bg-brand/10 text-brand border border-brand/20 mb-2">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <p className="text-xs text-muted">No audit log records match the current filter criteria.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-border-default bg-surface shadow-xs">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-border-default bg-surface-elevated/40 text-secondary font-medium uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-2.5 px-3 font-semibold w-12">#</th>
                <th className="py-2.5 px-3 font-semibold">Timestamp</th>
                <th className="py-2.5 px-3 font-semibold">Action</th>
                <th className="py-2.5 px-3 font-semibold">Entity Type</th>
                <th className="py-2.5 px-3 font-semibold">Actor</th>
                <th className="py-2.5 px-3 font-semibold">IP Address</th>
                <th className="py-2.5 px-3 font-semibold text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {logs.map((log) => (
                <tr
                  key={log.id}
                  onClick={() => setSelectedLog(log)}
                  className="hover:bg-surface-elevated/50 cursor-pointer transition-colors"
                >
                  <td className="py-2.5 px-3 font-mono text-muted">
                    {log.id}
                  </td>
                  <td className="py-2.5 px-3 text-secondary font-mono whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`inline-block rounded-xs border px-1.5 py-0.2 font-mono text-[11px] font-semibold ${getActionBadgeColor(
                        log.action
                      )}`}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-primary">
                    {log.entity_type}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-muted">
                    {log.actor_id ? log.actor_id.slice(0, 8) + '...' : 'system'}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-muted">
                    {log.ip_address || '127.0.0.1'}
                  </td>
                  <td className="py-2.5 px-3 text-right text-brand">
                    <ChevronRight className="w-4 h-4 ml-auto" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination Controls */}
          <div className="p-2.5 bg-surface-elevated/40 border-t border-border-default flex items-center justify-between text-xs">
            <span className="text-[11px] font-mono text-muted">
              Displaying {logs.length} latest audit records
            </span>
            <div className="flex items-center gap-2">
              {cursor !== undefined && (
                <button
                  type="button"
                  onClick={handleResetPagination}
                  className="rounded-xs border border-border-default bg-surface px-2.5 py-1 text-xs text-secondary hover:text-primary transition-colors"
                >
                  First Page
                </button>
              )}
              {logs.length >= 25 && (
                <button
                  type="button"
                  onClick={handleNextPage}
                  className="rounded-xs border border-border-default bg-surface px-2.5 py-1 text-xs font-medium text-primary hover:bg-surface-elevated shadow-xs transition-colors"
                >
                  Next Page (Older) →
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal */}
      {selectedLog && (
        <AuditDetailModal
          log={selectedLog}
          isOpen={!!selectedLog}
          onClose={() => setSelectedLog(null)}
        />
      )}
    </div>
  );
};
