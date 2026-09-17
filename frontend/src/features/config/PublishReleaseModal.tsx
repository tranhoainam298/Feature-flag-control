import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { configApi } from './api';
import { X, Send, AlertCircle, Info } from 'lucide-react';

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
        'Failed to publish release';
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
      <div className="w-full max-w-md rounded-md border border-border-default bg-surface p-5 shadow-xl space-y-3.5">
        <div className="flex items-center justify-between border-b border-border-subtle pb-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-xs bg-brand/10 text-brand border border-brand/20">
              <Send className="w-3.5 h-3.5" />
            </div>
            <h3 className="text-sm font-semibold text-primary">
              Publish Configuration Release
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xs p-1 text-muted hover:bg-surface-elevated hover:text-primary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="rounded-xs bg-brand/10 border border-brand/20 p-2.5 text-xs text-brand flex items-start gap-2">
          <Info className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            Publishing <strong>{pendingChangesCount}</strong> draft {pendingChangesCount === 1 ? 'change' : 'changes'} into an immutable, versioned configuration release.
          </div>
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-xs border border-status-danger/30 bg-status-danger/10 p-2.5 text-xs text-status-danger font-mono"
          >
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-[11px] font-medium text-secondary mb-1">
              Release Comment / Changelog
            </label>
            <textarea
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="e.g. Update database connection timeouts and enable retry policy"
              className="w-full rounded-xs border border-border-default bg-surface-elevated p-2.5 text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 border-t border-border-subtle pt-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xs border border-border-default bg-surface px-3 py-1.5 text-xs font-medium text-secondary hover:bg-surface-elevated hover:text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={publishMutation.isPending}
              className="rounded-xs bg-brand px-3.5 py-1.5 text-xs font-medium text-white hover:bg-brand-hover shadow-xs disabled:opacity-50 transition-colors"
            >
              {publishMutation.isPending ? 'Publishing...' : 'Confirm & Publish'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
