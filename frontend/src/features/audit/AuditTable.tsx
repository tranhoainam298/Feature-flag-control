import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { auditApi } from './api';
import { AuditLogItem } from '../../types';
import { AuditDetailModal } from './AuditDetailModal';
import { Search, Filter, ShieldAlert, ChevronRight, RefreshCw } from 'lucide-react';
import { SkeletonTable } from '../../components/ui/SkeletonTable';

export const AuditTable: React.FC = () => {
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
    queryKey: ['audit-logs', actionQuery, entityType, cursor],
    queryFn: () =>
      auditApi.listAuditLogs({
        action: actionQuery || undefined,
        entityType: entityType !== 'ALL' ? entityType : undefined,
        limit: 25,
        cursor,
      }),
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
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    }
    if (action.includes('updated') || action.includes('toggle')) {
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    }
    if (action.includes('deleted') || action.includes('rollback')) {
      return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    }
    return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[var(--surface)] p-3 rounded-xl border border-[var(--border)]">
        <div className="flex flex-wrap items-center gap-2 flex-1">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[var(--text-tertiary)]" />
            <input
              type="text"
              placeholder="Lọc theo hành động (VD: flag, config, release)..."
              value={actionQuery}
              onChange={(e) => {
                setActionQuery(e.target.value);
                handleResetPagination();
              }}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] pl-9 pr-3 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-tertiary)] focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-[var(--text-tertiary)]" />
            <select
              value={entityType}
              onChange={(e) => {
                setEntityType(e.target.value);
                handleResetPagination();
              }}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-1.5 text-xs text-[var(--text-primary)] focus:outline-none"
            >
              <option value="ALL">Tất cả đối tượng</option>
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
          className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]"
          title="Tải lại nhật ký"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Table */}
      {isLoading ? (
        <SkeletonTable rows={8} columns={5} />
      ) : isError ? (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-400">
          Không thể tải danh sách nhật ký Audit.
        </div>
      ) : logs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-12 text-center">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-400 mb-2">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <p className="text-xs text-[var(--text-tertiary)]">Không có bản ghi audit nào phù hợp với bộ lọc.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-sm">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[var(--border)] bg-[var(--surface-sunken)] text-[var(--text-secondary)]">
              <tr>
                <th className="py-2.5 px-3 font-semibold w-12">#</th>
                <th className="py-2.5 px-3 font-semibold">Thời gian</th>
                <th className="py-2.5 px-3 font-semibold">Hành động (Action)</th>
                <th className="py-2.5 px-3 font-semibold">Loại đối tượng</th>
                <th className="py-2.5 px-3 font-semibold">Người thao tác</th>
                <th className="py-2.5 px-3 font-semibold">IP Address</th>
                <th className="py-2.5 px-3 font-semibold text-right">Chi tiết</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {logs.map((log) => (
                <tr
                  key={log.id}
                  onClick={() => setSelectedLog(log)}
                  className="hover:bg-[var(--surface-hover)] cursor-pointer transition-colors"
                >
                  <td className="py-2.5 px-3 font-mono text-[var(--text-tertiary)]">
                    {log.id}
                  </td>
                  <td className="py-2.5 px-3 text-[var(--text-secondary)] whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`inline-block rounded border px-2 py-0.5 font-mono text-[11px] font-semibold ${getActionBadgeColor(
                        log.action
                      )}`}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[var(--text-primary)]">
                    {log.entity_type}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[var(--text-tertiary)]">
                    {log.actor_id ? log.actor_id.slice(0, 8) + '...' : 'system'}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[var(--text-tertiary)]">
                    {log.ip_address || '127.0.0.1'}
                  </td>
                  <td className="py-2.5 px-3 text-right text-indigo-400">
                    <ChevronRight className="w-4 h-4 ml-auto" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination Controls */}
          <div className="p-3 bg-[var(--surface-sunken)] border-t border-[var(--border)] flex items-center justify-between text-xs">
            <span className="text-[var(--text-tertiary)]">
              Đang hiển thị {logs.length} bản ghi gần nhất
            </span>
            <div className="flex items-center gap-2">
              {cursor !== undefined && (
                <button
                  type="button"
                  onClick={handleResetPagination}
                  className="rounded border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
                >
                  Về trang đầu
                </button>
              )}
              {logs.length >= 25 && (
                <button
                  type="button"
                  onClick={handleNextPage}
                  className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-hover)] shadow-xs"
                >
                  Trang kế tiếp (Cũ hơn) →
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
