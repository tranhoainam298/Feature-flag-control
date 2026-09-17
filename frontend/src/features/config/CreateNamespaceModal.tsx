import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { configApi } from './api';
import { X } from 'lucide-react';

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
        'Không thể tạo namespace';
      setErrorMsg(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg('Tên namespace không được để trống');
      return;
    }
    createMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">
            Tạo Config Namespace mới
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            <X className="w-4 h-4" />
          </button>
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
              Tên Namespace *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="VD: application, payment-service, auth"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2 text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Định dạng (Format)
            </label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as any)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2 text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
            >
              <option value="json">JSON</option>
              <option value="yaml">YAML</option>
              <option value="properties">PROPERTIES</option>
            </select>
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
              disabled={createMutation.isPending}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm disabled:opacity-50"
            >
              {createMutation.isPending ? 'Đang tạo...' : 'Tạo Namespace'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
