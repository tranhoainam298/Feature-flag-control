import React from 'react';
import { AuditLogItem } from '../../types';
import { X, Shield, Terminal } from 'lucide-react';

interface AuditDetailModalProps {
  log: AuditLogItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export const AuditDetailModal: React.FC<AuditDetailModalProps> = ({
  log,
  isOpen,
  onClose,
}) => {
  if (!isOpen || !log) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-4xl rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                Chi tiết Audit Log #{log.id} — <span className="font-mono text-indigo-400">{log.action}</span>
              </h3>
              <p className="text-xs text-[var(--text-tertiary)]">
                Ghi nhận lúc: {new Date(log.created_at).toLocaleString()}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Metadata info */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[var(--surface-sunken)] p-3 rounded-lg border border-[var(--border)] text-xs">
          <div>
            <span className="text-[var(--text-tertiary)]">Loại đối tượng:</span>
            <div className="font-mono font-semibold text-[var(--text-primary)] mt-0.5">
              {log.entity_type}
            </div>
          </div>
          <div>
            <span className="text-[var(--text-tertiary)]">ID đối tượng:</span>
            <div className="font-mono text-[var(--text-secondary)] truncate mt-0.5" title={log.entity_id || ''}>
              {log.entity_id || 'N/A'}
            </div>
          </div>
          <div>
            <span className="text-[var(--text-tertiary)]">Người thao tác (Actor ID):</span>
            <div className="font-mono text-[var(--text-secondary)] truncate mt-0.5" title={log.actor_id || ''}>
              {log.actor_id ? log.actor_id.slice(0, 8) + '...' : 'System'}
            </div>
          </div>
          <div>
            <span className="text-[var(--text-tertiary)]">IP Address:</span>
            <div className="font-mono text-[var(--text-secondary)] mt-0.5">
              {log.ip_address || '127.0.0.1'}
            </div>
          </div>
        </div>

        {/* Before / After Diff */}
        <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Before Column */}
          <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3 flex flex-col">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-400 mb-2 border-b border-rose-500/20 pb-1.5">
              <Terminal className="w-3.5 h-3.5" />
              <span>Trạng thái trước (Before)</span>
            </div>
            <pre className="flex-1 overflow-y-auto max-h-72 rounded bg-[var(--surface-sunken)] p-2.5 font-mono text-[11px] text-[var(--text-secondary)] border border-[var(--border)]">
              {log.before ? JSON.stringify(log.before, null, 2) : '// Không có dữ liệu trước thay đổi'}
            </pre>
          </div>

          {/* After Column */}
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 flex flex-col">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 mb-2 border-b border-emerald-500/20 pb-1.5">
              <Terminal className="w-3.5 h-3.5" />
              <span>Trạng thái sau (After)</span>
            </div>
            <pre className="flex-1 overflow-y-auto max-h-72 rounded bg-[var(--surface-sunken)] p-2.5 font-mono text-[11px] text-emerald-300/90 border border-[var(--border)]">
              {log.after ? JSON.stringify(log.after, null, 2) : '// Không có dữ liệu sau thay đổi'}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-[var(--border)] pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
