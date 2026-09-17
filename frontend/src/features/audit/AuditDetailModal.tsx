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
      <div className="w-full max-w-4xl rounded-md border border-border-default bg-surface p-5 shadow-2xl space-y-3.5 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-subtle pb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-xs bg-brand/10 text-brand border border-brand/20">
              <Shield className="w-3.5 h-3.5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-primary">
                Audit Record #{log.id} — <span className="font-mono text-brand">{log.action}</span>
              </h3>
              <p className="text-[11px] text-muted font-mono">
                Recorded at: {new Date(log.created_at).toLocaleString()}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-xs p-1 text-muted hover:bg-surface-elevated hover:text-primary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Metadata info */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 bg-surface-elevated/40 p-2.5 rounded-xs border border-border-default text-xs">
          <div>
            <span className="text-[10px] text-muted uppercase tracking-wider block">Entity Type:</span>
            <div className="font-mono font-semibold text-primary mt-0.5">
              {log.entity_type}
            </div>
          </div>
          <div>
            <span className="text-[10px] text-muted uppercase tracking-wider block">Entity ID:</span>
            <div className="font-mono text-secondary truncate mt-0.5" title={log.entity_id || ''}>
              {log.entity_id || 'N/A'}
            </div>
          </div>
          <div>
            <span className="text-[10px] text-muted uppercase tracking-wider block">Actor ID:</span>
            <div className="font-mono text-secondary truncate mt-0.5" title={log.actor_id || ''}>
              {log.actor_id ? log.actor_id.slice(0, 8) + '...' : 'System'}
            </div>
          </div>
          <div>
            <span className="text-[10px] text-muted uppercase tracking-wider block">IP Address:</span>
            <div className="font-mono text-secondary mt-0.5">
              {log.ip_address || '127.0.0.1'}
            </div>
          </div>
        </div>

        {/* Before / After Diff */}
        <div className="flex-1 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Before Column */}
          <div className="rounded-xs border border-status-danger/20 bg-status-danger/5 p-2.5 flex flex-col">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-status-danger mb-2 border-b border-status-danger/20 pb-1.5">
              <Terminal className="w-3.5 h-3.5" />
              <span>Before State (Snapshot)</span>
            </div>
            <pre className="flex-1 overflow-y-auto max-h-72 rounded-xs bg-surface-elevated p-2.5 font-mono text-[11px] text-secondary border border-border-default">
              {log.before ? JSON.stringify(log.before, null, 2) : '// No state recorded prior to mutation'}
            </pre>
          </div>

          {/* After Column */}
          <div className="rounded-xs border border-status-success/20 bg-status-success/5 p-2.5 flex flex-col">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-status-success mb-2 border-b border-status-success/20 pb-1.5">
              <Terminal className="w-3.5 h-3.5" />
              <span>After State (Snapshot)</span>
            </div>
            <pre className="flex-1 overflow-y-auto max-h-72 rounded-xs bg-surface-elevated p-2.5 font-mono text-[11px] text-status-success/90 border border-border-default">
              {log.after ? JSON.stringify(log.after, null, 2) : '// No post-mutation state recorded'}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-border-subtle pt-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xs border border-border-default bg-surface px-3 py-1.5 text-xs font-medium text-secondary hover:bg-surface-elevated hover:text-primary transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
