import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { segmentApi } from './api';
import { ConditionGroupData } from '../../types';
import { ConditionGroup } from '../../components/conditions/ConditionGroup';
import { X, AlertCircle } from 'lucide-react';

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
        'Failed to create audience segment';
      setErrorMsg(typeof msg === 'object' ? JSON.stringify(msg) : String(msg));
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !key.trim()) {
      setErrorMsg('Name and Key are required fields');
      return;
    }
    createMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-2xl rounded-md border border-border-default bg-surface p-5 shadow-xl space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-border-subtle pb-3">
          <div>
            <h3 className="text-sm font-semibold text-primary">
              Create Audience Segment
            </h3>
            <p className="text-[11px] text-muted">
              Define reusable targeting criteria to match user groups across flags.
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

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-[11px] font-medium text-secondary mb-1">
                Segment Name *
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="e.g. APAC VIP Users"
                className="w-full rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1.5 text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-secondary mb-1">
                Segment Key (slug a-z, 0-9, -, _) *
              </label>
              <input
                type="text"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="apac-vip-users"
                className="w-full rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1.5 font-mono text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
                pattern="^[a-z0-9_-]+$"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-secondary mb-1">
              Description (optional)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. High tier paying customers located in APAC"
              className="w-full rounded-xs border border-border-default bg-surface-elevated px-2.5 py-1.5 text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-secondary mb-1.5">
              Targeting Criteria (Condition Clauses)
            </label>
            <ConditionGroup
              group={conditions}
              onChange={setConditions}
              disabled={createMutation.isPending}
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
              disabled={createMutation.isPending}
              className="rounded-xs bg-brand px-3.5 py-1.5 text-xs font-medium text-white hover:bg-brand-hover shadow-xs disabled:opacity-50 transition-colors"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Segment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
