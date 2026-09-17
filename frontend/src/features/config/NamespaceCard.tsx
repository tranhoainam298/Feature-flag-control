import React from 'react';
import { Link } from 'react-router-dom';
import { ConfigNamespace } from '../../types';
import { Database, ArrowRight, FileCode } from 'lucide-react';

interface NamespaceCardProps {
  namespace: ConfigNamespace;
}

export const NamespaceCard: React.FC<NamespaceCardProps> = ({ namespace }) => {
  return (
    <div className="rounded-md border border-border-default bg-surface p-3.5 shadow-xs hover:border-border-hover transition-colors flex flex-col justify-between group">
      <div className="space-y-2.5">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-xs bg-brand/10 text-brand border border-brand/20 group-hover:bg-brand/15 transition-colors">
              <Database className="w-3.5 h-3.5" />
            </div>
            <div>
              <h3 className="text-xs font-semibold text-primary group-hover:text-brand transition-colors">
                {namespace.name}
              </h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <FileCode className="w-3 h-3 text-muted" />
                <span className="text-[10px] font-mono uppercase text-muted">
                  {namespace.format}
                </span>
              </div>
            </div>
          </div>

          <span
            className={`rounded-xs px-1.5 py-0.5 text-[10px] font-semibold font-mono ${
              namespace.current_release_id
                ? 'bg-status-success/10 text-status-success border border-status-success/20'
                : 'bg-status-warning/10 text-status-warning border border-status-warning/20'
            }`}
          >
            {namespace.current_release_id ? 'Active Release' : 'Draft Only'}
          </span>
        </div>

        <p className="text-xs text-secondary line-clamp-2">
          Centralized configuration parameters, runtime flags, and encrypted secrets for this service.
        </p>
      </div>

      <div className="mt-3 pt-2.5 border-t border-border-subtle flex items-center justify-between">
        <span className="text-[11px] font-mono text-muted">
          {new Date(namespace.created_at).toLocaleDateString()}
        </span>

        <Link
          to={`/config/${namespace.id}`}
          className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:text-brand-hover transition-colors"
        >
          <span>Manage Config</span>
          <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
};
