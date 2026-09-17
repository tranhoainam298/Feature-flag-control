import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ConfigDraftTable } from '../features/config/ConfigDraftTable';
import { ReleaseHistoryTable } from '../features/config/ReleaseHistoryTable';
import { ArrowLeft, Database, Sliders, History } from 'lucide-react';

export const ConfigDetailPage: React.FC = () => {
  const { namespaceId } = useParams<{ namespaceId: string }>();
  const [activeTab, setActiveTab] = useState<'draft' | 'history'>('draft');

  if (!namespaceId) return null;

  return (
    <div className="space-y-4">
      {/* Back link */}
      <div>
        <Link
          to="/config"
          className="inline-flex items-center gap-1.5 text-xs text-secondary hover:text-primary transition-colors font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Configuration Namespaces</span>
        </Link>
      </div>

      {/* Namespace Header */}
      <div className="rounded-md border border-border-default bg-surface p-3.5 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xs bg-brand/10 text-brand border border-brand/20">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-primary">
              Namespace: <span className="font-mono text-brand">{namespaceId.slice(0, 8)}...</span>
            </h2>
            <p className="text-[11px] text-muted mt-0.5">
              Manage draft parameters, preview diffs, publish releases, and rollback version history.
            </p>
          </div>
        </div>

        {/* Tab switchers */}
        <div className="flex items-center gap-1 bg-surface-elevated p-0.5 rounded-xs border border-border-default">
          <button
            type="button"
            onClick={() => setActiveTab('draft')}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xs transition-colors cursor-pointer ${
              activeTab === 'draft'
                ? 'bg-brand text-white font-semibold shadow-xs'
                : 'text-secondary hover:text-primary'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Draft Configuration</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xs transition-colors cursor-pointer ${
              activeTab === 'history'
                ? 'bg-brand text-white font-semibold shadow-xs'
                : 'text-secondary hover:text-primary'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Release History</span>
          </button>
        </div>
      </div>

      {/* Tab content */}
      {activeTab === 'draft' ? (
        <ConfigDraftTable namespaceId={namespaceId} />
      ) : (
        <ReleaseHistoryTable namespaceId={namespaceId} />
      )}
    </div>
  );
};
