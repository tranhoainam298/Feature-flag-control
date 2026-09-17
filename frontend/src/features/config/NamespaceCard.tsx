import React from 'react';
import { Link } from 'react-router-dom';
import { ConfigNamespace } from '../../types';
import { Database, ArrowRight, FileCode } from 'lucide-react';

interface NamespaceCardProps {
  namespace: ConfigNamespace;
}

export const NamespaceCard: React.FC<NamespaceCardProps> = ({ namespace }) => {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm hover:border-indigo-500/40 transition-all flex flex-col justify-between group">
      <div className="space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 group-hover:bg-indigo-500/20 transition-colors">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[var(--text-primary)] group-hover:text-indigo-400 transition-colors">
                {namespace.name}
              </h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <FileCode className="w-3 h-3 text-[var(--text-tertiary)]" />
                <span className="text-[11px] font-mono uppercase text-[var(--text-tertiary)]">
                  {namespace.format}
                </span>
              </div>
            </div>
          </div>

          <span
            className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
              namespace.current_release_id
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
            }`}
          >
            {namespace.current_release_id ? 'Đã phát hành' : 'Chưa có release'}
          </span>
        </div>

        <p className="text-xs text-[var(--text-secondary)]">
          Quản lý tập trung các biến môi trường, cấu hình runtime và secret cho service này.
        </p>
      </div>

      <div className="mt-5 pt-3 border-t border-[var(--border)] flex items-center justify-between">
        <span className="text-[11px] text-[var(--text-tertiary)]">
          {new Date(namespace.created_at).toLocaleDateString()}
        </span>

        <Link
          to={`/config/${namespace.id}`}
          className="inline-flex items-center gap-1 text-xs font-medium text-indigo-400 hover:text-indigo-300"
        >
          <span>Mở cấu hình</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
};
