import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { configApi } from './api';
import { X, Send } from 'lucide-react';

interface PublishReleaseModalProps {
  namespaceId: string;
  isOpen: boolean;
  onClose: () => void;
  pendingChangesCount: number;
}

export const PublishReleaseModal: React.FC<PublishReleaseModalProps> = ({
  namespaceId,
  isOpen,
  onClose,
  pendingChangesCount,
}) => {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const publishMutation = useMutation({
    mutationFn: () => configApi.publishRelease(namespaceId, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-draft-items', namespaceId] });
      queryClient.invalidateQueries({ queryKey: ['config-pending-diff', namespaceId] });
      queryClient.invalidateQueries({ queryKey: ['config-releases', namespaceId] });
      onClose();
      setComment('');
      setErrorMsg(null);
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Không thể phát hành release';
      setErrorMsg(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    publishMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
              <Send className="w-3.5 h-3.5" />
            </div>
            <h3 className="text-base font-semibold text-[var(--text-primary)]">
              Phát hành cấu hình (Publish)
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="rounded-lg bg-indigo-500/10 border border-indigo-500/20 p-3 text-xs text-indigo-300">
          Bạn đang phát hành <strong>{pendingChangesCount}</strong> thay đổi từ bản nháp thành phiên bản cấu hình chính thức (Release).
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-400 font-mono"
          >
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Ghi chú phát hành (Release comment)
            </label>
            <textarea
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="VD: Cập nhật timeout kết nối DB và cấu hình payment retry..."
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-2.5 text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 border-t border-[var(--border)] pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={publishMutation.isPending}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm disabled:opacity-50"
            >
              {publishMutation.isPending ? 'Đang phát hành...' : 'Xác nhận Phát hành'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
