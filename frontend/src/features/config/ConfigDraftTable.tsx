import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { configApi } from './api';
import { ConfigItemInput } from '../../types';
import { ConfigDiffModal } from './ConfigDiffModal';
import { PublishReleaseModal } from './PublishReleaseModal';
import { Eye, EyeOff, Plus, Trash2, Save, Send, GitCompare, Lock, AlertCircle, CheckCircle2 } from 'lucide-react';
import { SkeletonTable } from '../../components/ui/SkeletonTable';

interface ConfigDraftTableProps {
  namespaceId: string;
}

export const ConfigDraftTable: React.FC<ConfigDraftTableProps> = ({ namespaceId }) => {
  const queryClient = useQueryClient();
  const [revealSecrets, setRevealSecrets] = useState(false);
  const [items, setItems] = useState<ConfigItemInput[]>([]);
  const [isDiffOpen, setIsDiffOpen] = useState(false);
  const [isPublishOpen, setIsPublishOpen] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Fetch draft items (with optional reveal)
  const {
    data: remoteItems,
    isLoading: isItemsLoading,
    isError: isItemsError,
  } = useQuery({
    queryKey: ['config-draft-items', namespaceId, revealSecrets],
    queryFn: () => configApi.listDraftItems(namespaceId, revealSecrets),
    enabled: !!namespaceId,
  });

  // Fetch pending diff
  const { data: pendingDiff } = useQuery({
    queryKey: ['config-pending-diff', namespaceId],
    queryFn: () => configApi.getPendingDiff(namespaceId),
    enabled: !!namespaceId,
  });

  useEffect(() => {
    if (remoteItems) {
      setItems(
        remoteItems.map((it) => ({
          key: it.key,
          value: it.value,
          value_type: it.value_type,
          is_secret: it.is_secret,
          json_schema: it.json_schema,
          comment: it.comment,
        }))
      );
    }
  }, [remoteItems]);

  const updateMutation = useMutation({
    mutationFn: (newItems: ConfigItemInput[]) =>
      configApi.updateDraftItems(namespaceId, newItems),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-draft-items', namespaceId] });
      queryClient.invalidateQueries({ queryKey: ['config-pending-diff', namespaceId] });
      setSaveSuccess('Draft configuration saved successfully');
      setSaveError(null);
      setTimeout(() => setSaveSuccess(null), 4000);
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Failed to save draft';
      setSaveError(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
      setSaveSuccess(null);
    },
  });

  const handleRowChange = (index: number, field: keyof ConfigItemInput, val: any) => {
    const next = [...items];
    next[index] = { ...next[index], [field]: val };
    setItems(next);
  };

  const handleAddItem = () => {
    const newItem: ConfigItemInput = {
      key: '',
      value: '',
      value_type: 'string',
      is_secret: false,
      comment: '',
    };
    setItems([...items, newItem]);
  };

  const handleDeleteItem = (index: number) => {
    setItems(items.filter((_, idx) => idx !== index));
  };

  const handleSave = () => {
    setSaveError(null);
    for (let i = 0; i < items.length; i++) {
      if (!items[i].key.trim()) {
        setSaveError(`Row #${i + 1} has an empty key. Key is required.`);
        return;
      }
    }
    updateMutation.mutate(items);
  };

  const pendingCount =
    (Object.keys(pendingDiff?.added || {}).length) +
    (Object.keys(pendingDiff?.changed || {}).length) +
    (Object.keys(pendingDiff?.removed || {}).length);

  if (isItemsLoading) return <SkeletonTable rows={5} columns={5} />;
  if (isItemsError) {
    return (
      <div className="rounded-md border border-status-danger/30 bg-status-danger/10 p-3 text-xs text-status-danger">
        Failed to load draft configuration items.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Top Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-surface p-2.5 rounded-md border border-border-default">
        <div className="flex items-center gap-2.5">
          {pendingCount > 0 ? (
            <span className="flex items-center gap-1.5 rounded-xs bg-status-warning/10 border border-status-warning/30 px-2.5 py-1 text-xs font-semibold text-status-warning">
              <span className="h-1.5 w-1.5 rounded-full bg-status-warning animate-pulse"></span>
              {pendingCount} unpublished {pendingCount === 1 ? 'change' : 'changes'}
            </span>
          ) : (
            <span className="flex items-center gap-1.5 rounded-xs bg-status-success/10 border border-status-success/30 px-2.5 py-1 text-xs font-medium text-status-success">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Synchronized with active release
            </span>
          )}

          <button
            type="button"
            onClick={() => setIsDiffOpen(true)}
            disabled={!pendingDiff}
            className="flex items-center gap-1.5 rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1 text-xs font-medium text-secondary hover:text-primary transition-colors disabled:opacity-50"
          >
            <GitCompare className="w-3.5 h-3.5 text-brand" />
            <span>View Diff</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setRevealSecrets(!revealSecrets)}
            className="flex items-center gap-1.5 rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1 text-xs font-medium text-secondary hover:text-primary transition-colors"
          >
            {revealSecrets ? (
              <>
                <EyeOff className="w-3.5 h-3.5 text-status-warning" />
                <span>Mask Secrets</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5 text-brand" />
                <span>Reveal Secrets</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="flex items-center gap-1.5 rounded-xs border border-brand/40 bg-brand/10 px-3 py-1 text-xs font-medium text-brand hover:bg-brand/20 disabled:opacity-40 transition-colors cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{updateMutation.isPending ? 'Saving...' : 'Save Draft'}</span>
          </button>

          <button
            type="button"
            onClick={() => setIsPublishOpen(true)}
            disabled={pendingCount === 0}
            className="flex items-center gap-1.5 rounded-xs bg-brand px-3.5 py-1 text-xs font-medium text-white hover:bg-brand-hover shadow-xs disabled:opacity-40 transition-colors cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Publish Release</span>
          </button>
        </div>
      </div>

      {saveSuccess && (
        <div className="flex items-center gap-2 rounded-xs border border-status-success/30 bg-status-success/10 p-2.5 text-xs text-status-success">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          <span>{saveSuccess}</span>
        </div>
      )}

      {saveError && (
        <div className="flex items-center gap-2 rounded-xs border border-status-danger/30 bg-status-danger/10 p-2.5 text-xs text-status-danger font-mono">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{saveError}</span>
        </div>
      )}

      {/* Editable Items Table */}
      <div className="overflow-hidden rounded-md border border-border-default bg-surface shadow-xs">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-border-default bg-surface-elevated/40 text-secondary font-medium uppercase tracking-wider text-[10px]">
            <tr>
              <th className="py-2.5 px-3 font-semibold w-1/4">Key</th>
              <th className="py-2.5 px-3 font-semibold w-1/3">Value</th>
              <th className="py-2.5 px-3 font-semibold w-24">Type</th>
              <th className="py-2.5 px-3 font-semibold w-20 text-center">Secret</th>
              <th className="py-2.5 px-3 font-semibold">Comment</th>
              <th className="py-2.5 px-3 font-semibold w-12 text-center">Delete</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {items.map((item, idx) => (
              <tr key={`item-${idx}`} className="hover:bg-surface-elevated/50 transition-colors">
                <td className="py-2 px-3">
                  <input
                    type="text"
                    value={item.key}
                    onChange={(e) => handleRowChange(idx, 'key', e.target.value)}
                    placeholder="database_url"
                    className="w-full rounded-xs border border-border-default bg-surface-elevated px-2 py-1 font-mono text-xs text-primary focus:border-brand focus-visible:outline-none"
                  />
                </td>

                <td className="py-2 px-3">
                  <div className="relative">
                    <input
                      type={item.is_secret && !revealSecrets ? 'password' : 'text'}
                      value={item.value}
                      onChange={(e) => handleRowChange(idx, 'value', e.target.value)}
                      placeholder={item.is_secret ? '••••••••' : 'Configuration value'}
                      className={`w-full rounded-xs border border-border-default bg-surface-elevated px-2 py-1 font-mono text-xs text-primary focus:border-brand focus-visible:outline-none ${
                        item.is_secret ? 'pr-7' : ''
                      }`}
                    />
                    {item.is_secret && (
                      <Lock className="absolute right-2 top-2 w-3 h-3 text-status-warning/70 pointer-events-none" />
                    )}
                  </div>
                </td>

                <td className="py-2 px-3">
                  <select
                    value={item.value_type}
                    onChange={(e) => handleRowChange(idx, 'value_type', e.target.value as any)}
                    className="w-full rounded-xs border border-border-default bg-surface-elevated px-2 py-1 text-xs text-primary focus:outline-none focus:border-brand"
                  >
                    <option value="string">STRING</option>
                    <option value="number">NUMBER</option>
                    <option value="boolean">BOOLEAN</option>
                    <option value="json">JSON</option>
                  </select>
                </td>

                <td className="py-2 px-3 text-center">
                  <input
                    type="checkbox"
                    checked={item.is_secret}
                    onChange={(e) => handleRowChange(idx, 'is_secret', e.target.checked)}
                    className="h-3.5 w-3.5 rounded-xs border-border-default text-brand focus:ring-brand accent-brand cursor-pointer"
                    title="Mark as Secret (AES-256-GCM encrypted)"
                  />
                </td>

                <td className="py-2 px-3">
                  <input
                    type="text"
                    value={item.comment || ''}
                    onChange={(e) => handleRowChange(idx, 'comment', e.target.value)}
                    placeholder="Description or context..."
                    className="w-full rounded-xs border border-border-default bg-surface-elevated px-2 py-1 text-xs text-secondary focus:outline-none focus:border-brand"
                  />
                </td>

                <td className="py-2 px-3 text-center">
                  <button
                    type="button"
                    onClick={() => handleDeleteItem(idx)}
                    className="rounded-xs p-1 text-muted hover:bg-status-danger/10 hover:text-status-danger transition-colors"
                    title="Delete key"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="p-2.5 bg-surface-elevated/40 border-t border-border-default flex justify-between items-center">
          <button
            type="button"
            onClick={handleAddItem}
            className="flex items-center gap-1.5 text-xs font-medium text-brand hover:text-brand-hover transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Configuration Key</span>
          </button>
          <span className="text-[11px] font-mono text-muted">
            Total: {items.length} {items.length === 1 ? 'key' : 'keys'}
          </span>
        </div>
      </div>

      {/* Diff Modal */}
      {isDiffOpen && pendingDiff && (
        <ConfigDiffModal
          diff={pendingDiff}
          isOpen={isDiffOpen}
          onClose={() => setIsDiffOpen(false)}
          onPublishClick={() => setIsPublishOpen(true)}
        />
      )}

      {/* Publish Modal */}
      {isPublishOpen && (
        <PublishReleaseModal
          namespaceId={namespaceId}
          isOpen={isPublishOpen}
          onClose={() => setIsPublishOpen(false)}
          pendingChangesCount={pendingCount}
        />
      )}
    </div>
  );
};
