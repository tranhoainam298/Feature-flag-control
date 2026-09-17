import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { segmentApi } from './api';
import { ConditionGroupData } from '../../types';
import { ConditionGroup } from '../../components/conditions/ConditionGroup';
import { X } from 'lucide-react';

interface CreateSegmentModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const CreateSegmentModal: React.FC<CreateSegmentModalProps> = ({
  projectId,
  isOpen,
  onClose,
}) => {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [key, setKey] = useState('');
  const [description, setDescription] = useState('');
  const [conditions, setConditions] = useState<ConditionGroupData>({
    operator: 'AND',
    conditions: [{ attribute: 'country', operator: 'EQ', value: 'VN' }],
  });
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleNameChange = (val: string) => {
    setName(val);
    // Auto-generate key if key hasn't been manually diverged
    const slug = val
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
    setKey(slug);
  };

  const createMutation = useMutation({
    mutationFn: () =>
      segmentApi.createSegment(projectId, {
        name,
        key,
        description: description || undefined,
        conditions,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments', projectId] });
      onClose();
      setName('');
      setKey('');
      setDescription('');
      setErrorMsg(null);
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Không thể tạo segment';
      setErrorMsg(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !key.trim()) {
      setErrorMsg('Tên và Mã định danh (key) không được để trống');
      return;
    }
    createMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-2xl rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">
            Tạo Phân khúc Người dùng (Segment) mới
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
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                Tên Segment *
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="VD: Người dùng Việt Nam VIP"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2 text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
                Mã Key (slug a-z, 0-9, -, _) *
              </label>
              <input
                type="text"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="vn-vip-users"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2 font-mono text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
                pattern="^[a-z0-9_-]+$"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Mô tả mục đích
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="VD: Nhóm người dùng có gói premium và định vị tại VN"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] px-3 py-2 text-xs text-[var(--text-primary)] focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-2">
              Bộ điều kiện Segment (Áp dụng toán tử logic)
            </label>
            <ConditionGroup
              group={conditions}
              onChange={setConditions}
              disabled={createMutation.isPending}
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
              disabled={createMutation.isPending}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm disabled:opacity-50"
            >
              {createMutation.isPending ? 'Đang tạo...' : 'Tạo Segment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
