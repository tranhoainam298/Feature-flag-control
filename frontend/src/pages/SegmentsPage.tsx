import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { segmentApi } from '../features/segments/api';
import { SegmentCard } from '../features/segments/SegmentCard';
import { CreateSegmentModal } from '../features/segments/CreateSegmentModal';
import { useApp } from '../context/AppContext';
import { Users, Plus, Search } from 'lucide-react';
import { SkeletonTable } from '../components/ui/SkeletonTable';
import { ErrorAlert } from '../components/ui/ErrorAlert';

export const SegmentsPage: React.FC = () => {
  const { currentProject } = useApp();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const projectId = currentProject?.id || '';

  const {
    data: segments = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['segments', projectId],
    queryFn: () => segmentApi.listSegments(projectId),
    enabled: !!projectId,
  });

  const deleteMutation = useMutation({
    mutationFn: (segmentId: string) => segmentApi.deleteSegment(projectId, segmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments', projectId] });
    },
  });

  const filteredSegments = segments.filter((s) => {
    const q = searchTerm.toLowerCase();
    return (
      s.name.toLowerCase().includes(q) ||
      s.key.toLowerCase().includes(q) ||
      (s.description && s.description.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-default pb-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-primary">
            Audience Segments
          </h1>
          <p className="mt-0.5 text-xs text-secondary">
            Reusable targeting groups evaluated by user context attributes to power targeting rules across feature flags.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-xs bg-brand px-3 py-1.5 text-xs font-medium text-white shadow-xs hover:bg-brand-hover transition-colors cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Create Segment</span>
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted" />
          <input
            type="text"
            placeholder="Search by name, key, or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-xs border border-border-default bg-surface pl-8 pr-3 py-1.5 text-xs text-primary placeholder:text-muted focus:border-brand focus-visible:outline-none"
          />
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <SkeletonTable rows={4} columns={3} />
      ) : isError ? (
        <ErrorAlert error={error || 'Failed to load segments'} onRetry={() => refetch()} />
      ) : filteredSegments.length === 0 ? (
        <div className="rounded-md border border-dashed border-border-default p-10 text-center bg-surface/50">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xs bg-brand/10 text-brand border border-brand/20 mb-2.5">
            <Users className="w-5 h-5" />
          </div>
          <h3 className="text-xs font-semibold text-primary">
            {searchTerm ? 'No matching segments found' : 'No audience segments created yet'}
          </h3>
          <p className="mt-1 text-xs text-muted max-w-sm mx-auto">
            Create reusable user groups with specific attribute rules to target users consistently across flags.
          </p>
          {!searchTerm && (
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="mt-3.5 inline-flex items-center gap-1.5 rounded-xs bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-hover transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create First Segment</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filteredSegments.map((segment) => (
            <SegmentCard
              key={segment.id}
              segment={segment}
              onDelete={(id) => deleteMutation.mutate(id)}
              disabled={deleteMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Create Modal */}
      {isCreateOpen && (
        <CreateSegmentModal
          projectId={projectId}
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
        />
      )}
    </div>
  );
};
