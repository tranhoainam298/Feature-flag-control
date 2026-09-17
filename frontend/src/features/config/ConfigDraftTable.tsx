import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { configApi } from './api';
import { ConfigItemInput } from '../../types';
import { ConfigDiffModal } from './ConfigDiffModal';
import { PublishReleaseModal } from './PublishReleaseModal';
import { Eye, EyeOff, Plus, Trash2, Save, Send, GitCompare, Lock } from 'lucide-react';
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
      setSaveSuccess('Đã lưu bản nháp thành công!');
      setSaveError(null);
      setTimeout(() => setSaveSuccess(null), 4000);
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Lỗi lưu bản nháp';
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
    // Basic validation: keys must not be empty
    for (let i = 0; i < items.length; i++) {
      if (!items[i].key.trim()) {
        setSaveError(`Dòng #${i + 1} chưa có Key. Key không được để trống!`);
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
      <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-400">
        Lỗi tải dữ liệu cấu hình nháp.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[var(--surface)] p-4 rounded-xl border border-[var(--border)]">
        <div className="flex items-center gap-3">
          {pendingCount > 0 ? (
            <span className="flex items-center gap-1.5 rounded-full bg-amber-500/15 border border-amber-500/30 px-3 py-1 text-xs font-semibold text-amber-300 animate-pulse">
              <span className="h-2 w-2 rounded-full bg-amber-400"></span>
              Có {pendingCount} thay đổi chưa phát hành
            </span>
          ) : (
            <span className="rounded-full bg-emerald-500/15 border border-emerald-500/30 px-3 py-1 text-xs font-medium text-emerald-300">
              Đồng bộ với bản phát hành hiện tại
            </span>
          )}

          <button
            type="button"
            onClick={() => setIsDiffOpen(true)}
            disabled={!pendingDiff}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            <GitCompare className="w-3.5 h-3.5 text-indigo-400" />
            <span>Xem thay đổi (Diff)</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setRevealSecrets(!revealSecrets)}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            {revealSecrets ? (
              <>
                <EyeOff className="w-3.5 h-3.5 text-amber-400" />
                <span>Ẩn secret</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5 text-indigo-400" />
                <span>Hiện secret</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="flex items-center gap-1.5 rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3.5 py-1.5 text-xs font-semibold text-indigo-400 hover:bg-indigo-500/20 disabled:opacity-40 cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{updateMutation.isPending ? 'Đang lưu...' : 'Lưu nháp'}</span>
          </button>

          <button
            type="button"
            onClick={() => setIsPublishOpen(true)}
            disabled={pendingCount === 0}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 shadow-sm disabled:opacity-40 cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Phát hành (Publish)</span>
          </button>
        </div>
      </div>

      {saveSuccess && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-400">
          {saveSuccess}
        </div>
      )}

      {saveError && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-400 font-mono">
          {saveError}
        </div>
      )}

      {/* Editable Items Table */}
      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-sm">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-[var(--border)] bg-[var(--surface-sunken)] text-[var(--text-secondary)]">
            <tr>
              <th className="py-2.5 px-3 font-semibold w-1/4">Key (Khóa)</th>
              <th className="py-2.5 px-3 font-semibold w-1/3">Giá trị (Value)</th>
              <th className="py-2.5 px-3 font-semibold w-24">Kiểu dữ liệu</th>
              <th className="py-2.5 px-3 font-semibold w-20 text-center">Bảo mật</th>
              <th className="py-2.5 px-3 font-semibold">Ghi chú</th>
              <th className="py-2.5 px-3 font-semibold w-12 text-center">Xóa</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {items.map((item, idx) => (
              <tr key={`item-${idx}`} className="hover:bg-[var(--surface-hover)]">
                <td className="py-2 px-3">
                  <input
                    type="text"
                    value={item.key}
                    onChange={(e) => handleRowChange(idx, 'key', e.target.value)}
                    placeholder="database_url"
                    className="w-full rounded border border-[var(--border)] bg-[var(--surface-sunken)] px-2 py-1 font-mono text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
                  />
                </td>

                <td className="py-2 px-3">
                  <div className="relative">
                    <input
                      type={item.is_secret && !revealSecrets ? 'password' : 'text'}
                      value={item.value}
                      onChange={(e) => handleRowChange(idx, 'value', e.target.value)}
                      placeholder={item.is_secret ? '••••••••' : 'Giá trị cấu hình'}
                      className={`w-full rounded border border-[var(--border)] bg-[var(--surface-sunken)] px-2 py-1 font-mono text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none ${
                        item.is_secret ? 'pr-7' : ''
                      }`}
                    />
                    {item.is_secret && (
                      <Lock className="absolute right-2 top-2 w-3 h-3 text-amber-400/70 pointer-events-none" />
                    )}
                  </div>
                </td>

                <td className="py-2 px-3">
                  <select
                    value={item.value_type}
                    onChange={(e) => handleRowChange(idx, 'value_type', e.target.value as any)}
                    className="w-full rounded border border-[var(--border)] bg-[var(--surface-sunken)] px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none"
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
                    className="h-4 w-4 rounded border-[var(--border)] text-indigo-600 focus:ring-indigo-500"
                    title="Đánh dấu là Secret bí mật (mã hóa AES-256-GCM)"
                  />
                </td>

                <td className="py-2 px-3">
                  <input
                    type="text"
                    value={item.comment || ''}
                    onChange={(e) => handleRowChange(idx, 'comment', e.target.value)}
                    placeholder="Mục đích dùng..."
                    className="w-full rounded border border-[var(--border)] bg-[var(--surface-sunken)] px-2 py-1 text-xs text-[var(--text-secondary)] focus:outline-none"
                  />
                </td>

                <td className="py-2 px-3 text-center">
                  <button
                    type="button"
                    onClick={() => handleDeleteItem(idx)}
                    className="rounded p-1 text-[var(--text-tertiary)] hover:bg-rose-500/10 hover:text-rose-400"
                    title="Xóa khóa này"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="p-3 bg-[var(--surface-sunken)] border-t border-[var(--border)] flex justify-between items-center">
          <button
            type="button"
            onClick={handleAddItem}
            className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Thêm khóa cấu hình (Key)</span>
          </button>
          <span className="text-xs text-[var(--text-tertiary)]">
            Tổng: {items.length} khóa
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
