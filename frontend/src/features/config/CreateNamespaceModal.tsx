import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { configApi } from './api';
import { X, AlertCircle } from 'lucide-react';

interface CreateNamespaceModalProps {
  envId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const CreateNamespaceModal: React.FC<CreateNamespaceModalProps> = ({
  envId,
  isOpen,
  onClose,
}) => {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [format, setFormat] = useState<'json' | 'yaml' | 'properties'>('json');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () => configApi.createNamespace(envId, { name, format }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-namespaces', envId] });
      onClose();
      setName('');
      setFormat('json');
      setErrorMsg(null);
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Failed to create configuration namespace';
      setErrorMsg(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg('Namespace name cannot be empty');
      return;
    }
    createMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-md border border-border-default bg-surface p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border-subtle pb-3">
          <div>
            <h3 className="text-sm font-semibold text-primary">
              Create Configuration Namespace
            </h3>
            <p className="text-[11px] text-muted">
              Define an isolated configuration scope for your application.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xs p-1 text-muted hover:bg-surface-elevated hover:text-primary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
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
              Namespace Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. application, payment-service, auth"
              className="w-full rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1.5 text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-secondary mb-1">
              Configuration Format
            </label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as any)}
              className="w-full rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1.5 text-xs text-primary focus:border-brand focus-visible:outline-none"
            >
              <option value="json">JSON</option>
              <option value="yaml">YAML</option>
              <option value="properties">PROPERTIES</option>
            </select>
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
              disabled={createMutation.isPending}
              className="rounded-xs bg-brand px-3.5 py-1.5 text-xs font-medium text-white hover:bg-brand-hover shadow-xs disabled:opacity-50 transition-colors"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Namespace'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
