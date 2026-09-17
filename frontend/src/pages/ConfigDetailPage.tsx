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
    <div className="space-y-6">
      {/* Back link */}
      <div>
        <Link
          to="/config"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Quay lại danh sách Namespace</span>
        </Link>
      </div>

      {/* Namespace Header */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[var(--text-primary)]">
              Namespace: <span className="font-mono text-indigo-400">{namespaceId.slice(0, 8)}...</span>
            </h2>
            <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
              Quản lý bản nháp, xuất bản release và rollback phiên bản cấu hình
            </p>
          </div>
        </div>

        {/* Tab switchers */}
        <div className="flex items-center gap-1 bg-[var(--surface-sunken)] p-1 rounded-lg border border-[var(--border)]">
          <button
            type="button"
            onClick={() => setActiveTab('draft')}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
              activeTab === 'draft'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Bản nháp hiện tại (Draft)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
              activeTab === 'history'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Lịch sử phát hành (Releases)</span>
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
