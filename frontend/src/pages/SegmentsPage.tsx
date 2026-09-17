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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
            Phân khúc Người dùng (Segments)
          </h1>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Tập hợp các nhóm người dùng theo điều kiện thuộc tính (VD: VIP, Quốc gia, Phiên bản app) để tái sử dụng trong các Rule.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Tạo Segment mới</span>
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[var(--text-tertiary)]" />
          <input
            type="text"
            placeholder="Tìm kiếm theo tên, mã key hoặc mô tả..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] pl-9 pr-3 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-tertiary)] focus:border-indigo-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <SkeletonTable rows={4} columns={3} />
      ) : isError ? (
        <ErrorAlert error={error || 'Lỗi tải danh sách segment'} onRetry={() => refetch()} />
      ) : filteredSegments.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-400 mb-3">
            <Users className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            {searchTerm ? 'Không tìm thấy segment phù hợp' : 'Chưa có segment nào trong dự án'}
          </h3>
          <p className="mt-1 text-xs text-[var(--text-tertiary)] max-w-sm mx-auto">
            Tạo segment để định nghĩa các nhóm người dùng phức tạp và tái sử dụng dễ dàng qua nhiều Feature Flag.
          </p>
          {!searchTerm && (
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Tạo Segment đầu tiên</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
