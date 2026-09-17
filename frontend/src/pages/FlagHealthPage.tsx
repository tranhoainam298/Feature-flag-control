import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { flagApi } from '../features/flags/api';
import { FlagHealthBadge } from '../features/flags/FlagHealthBadge';
import { FlagHealthItem } from '../types';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorAlert } from '../components/ui/ErrorAlert';
import { SkeletonTable } from '../components/ui/SkeletonTable';
import {
  HeartPulse,
  Search,
  SlidersHorizontal,
  Archive,
  AlertTriangle,
  CheckCircle2,
  PlayCircle,
  CircleDot,
  ArrowUpDown,
  ExternalLink,
  Info,
  Layers,
} from 'lucide-react';
import { cn } from '../lib/utils';

export const FlagHealthPage: React.FC = () => {
  const { currentProject } = useApp();
  const queryClient = useQueryClient();
  const projectId = currentProject?.id || '';

  // Local state for filters
  const [selectedState, setSelectedState] = useState<string>('ALL');
  const [minScore, setMinScore] = useState<number>(0);
  const [search, setSearch] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('score');

  // Archive modal state
  const [flagToArchive, setFlagToArchive] = useState<FlagHealthItem | null>(null);

  // Fetch health data
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['flag-health', projectId, selectedState, minScore, sortBy],
    queryFn: () =>
      flagApi.listFlagHealth(projectId, {
        state: selectedState !== 'ALL' ? selectedState : undefined,
        min_score: minScore > 0 ? minScore : undefined,
        sort: sortBy,
      }),
    enabled: !!projectId,
  });

  // Archive mutation
  const archiveMutation = useMutation({
    mutationFn: (flagId: string) => flagApi.archiveFlagByHealth(projectId, flagId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flag-health', projectId] });
      queryClient.invalidateQueries({ queryKey: ['flags', projectId] });
      setFlagToArchive(null);
    },
  });

  // Client-side search filtering on name/key
  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    if (!search.trim()) return data.items;
    const query = search.toLowerCase().trim();
    return data.items.filter(
      (item) =>
        item.flag_key.toLowerCase().includes(query) ||
        item.flag_name.toLowerCase().includes(query)
    );
  }, [data?.items, search]);

  const summary = data?.summary;

  const getScoreColor = (score: number) => {
    if (score < 30) return 'text-emerald-400 bg-emerald-500';
    if (score < 60) return 'text-amber-400 bg-amber-500';
    return 'text-rose-400 bg-rose-500';
  };

  const getScoreBorderColor = (score: number) => {
    if (score < 30) return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400';
    if (score < 60) return 'border-amber-500/20 bg-amber-500/10 text-amber-400';
    return 'border-rose-500/20 bg-rose-500/10 text-rose-400';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight text-primary">Flag Lifecycle & Health</h1>
            <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-medium bg-brand/10 text-brand border border-brand/20">
              Slice 14
            </span>
          </div>
          <p className="text-xs text-secondary mt-1">
            Theo dõi nợ kỹ thuật (technical debt), máy trạng thái vòng đời, và đề xuất dọn dẹp cờ tính năng trong{' '}
            <span className="text-primary font-medium">{currentProject?.name || 'Project'}</span>.
          </p>
        </div>
      </div>

      {/* Summary KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          <div className="p-3.5 rounded-md bg-surface border border-border-subtle flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-secondary" /> Tổng flag
            </span>
            <span className="text-xl font-bold font-mono text-primary mt-2">{summary.total}</span>
          </div>

          <div className="p-3.5 rounded-md bg-surface border border-border-subtle flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <CircleDot className="w-3.5 h-3.5 text-muted" /> Draft
            </span>
            <span className="text-xl font-bold font-mono text-secondary mt-2">{summary.draft_count}</span>
          </div>

          <div className="p-3.5 rounded-md bg-surface border border-border-subtle flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <PlayCircle className="w-3.5 h-3.5 text-emerald-400" /> Active
            </span>
            <span className="text-xl font-bold font-mono text-emerald-400 mt-2">{summary.active_count}</span>
          </div>

          <div className="p-3.5 rounded-md bg-surface border border-border-subtle flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" /> Rolled Out
            </span>
            <span className="text-xl font-bold font-mono text-sky-400 mt-2">{summary.rolled_out_count}</span>
          </div>

          <div className="p-3.5 rounded-md bg-surface border border-amber-500/20 bg-amber-500/5 flex flex-col justify-between">
            <span className="text-[11px] text-amber-400 font-medium flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Stale (Cần xử lý)
            </span>
            <span className="text-xl font-bold font-mono text-amber-400 mt-2">{summary.stale_count}</span>
          </div>

          <div className="p-3.5 rounded-md bg-surface border border-border-subtle flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <Archive className="w-3.5 h-3.5 text-rose-400" /> Archived
            </span>
            <span className="text-xl font-bold font-mono text-muted mt-2">{summary.archived_count}</span>
          </div>

          <div className="p-3.5 rounded-md bg-surface border border-border-subtle flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <HeartPulse className="w-3.5 h-3.5 text-brand" /> ĐTB Nợ Flag
            </span>
            <div className="flex items-baseline gap-1.5 mt-2">
              <span className={cn('text-xl font-bold font-mono', getScoreColor(summary.avg_score).split(' ')[0])}>
                {summary.avg_score}
              </span>
              <span className="text-[10px] text-muted font-mono">/100</span>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-surface p-3 rounded-md border border-border-subtle">
        {/* Search Input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="Tìm theo key hoặc tên flag..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-canvas border border-border-subtle rounded-md text-primary placeholder:text-muted focus:outline-hidden focus:border-brand transition-colors"
          />
        </div>

        {/* Filters Group */}
        <div className="flex items-center gap-2.5 w-full sm:w-auto overflow-x-auto">
          {/* State Filter */}
          <div className="flex items-center gap-1.5 text-xs text-secondary">
            <SlidersHorizontal className="w-3.5 h-3.5 text-muted shrink-0" />
            <select
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              className="bg-canvas border border-border-subtle rounded-md px-2.5 py-1.5 text-xs text-primary focus:outline-hidden focus:border-brand"
            >
              <option value="ALL">Tất cả trạng thái</option>
              <option value="DRAFT">DRAFT</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="ROLLED_OUT">ROLLED OUT</option>
              <option value="STALE">STALE (Cần thu hồi)</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>
          </div>

          {/* Min Score Filter */}
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="bg-canvas border border-border-subtle rounded-md px-2.5 py-1.5 text-xs text-primary focus:outline-hidden focus:border-brand"
          >
            <option value="0">Tất cả điểm nợ</option>
            <option value="30">Điểm nợ ≥ 30 (Vừa & Cao)</option>
            <option value="60">Điểm nợ ≥ 60 (Cao)</option>
          </select>

          {/* Sort By */}
          <div className="flex items-center gap-1 text-xs text-secondary">
            <ArrowUpDown className="w-3.5 h-3.5 text-muted shrink-0" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-canvas border border-border-subtle rounded-md px-2.5 py-1.5 text-xs text-primary focus:outline-hidden focus:border-brand"
            >
              <option value="score">Sắp xếp: Điểm nợ cao nhất</option>
              <option value="name">Sắp xếp: Tên A-Z</option>
              <option value="state">Sắp xếp: Trạng thái</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <SkeletonTable rows={5} columns={5} />
      ) : isError ? (
        <ErrorAlert
          title="Không tải được dữ liệu sức khỏe flag"
          error={error}
          onRetry={() => refetch()}
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={<HeartPulse className="w-6 h-6 text-muted" />}
          title="Không tìm thấy cờ tính năng nào"
          description="Không có cờ tính năng nào khớp với tiêu chí tìm kiếm hoặc bộ lọc hiện tại."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSelectedState('ALL');
                setMinScore(0);
                setSearch('');
              }}
            >
              Đặt lại bộ lọc
            </Button>
          }
        />
      ) : (
        <div className="border border-border-subtle rounded-md overflow-hidden bg-surface">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border-subtle bg-surface-subtle text-secondary font-medium uppercase tracking-wider text-[10px]">
                  <th className="py-2.5 px-4">Flag / Định danh</th>
                  <th className="py-2.5 px-3">Trạng thái</th>
                  <th className="py-2.5 px-3 w-52">Điểm nợ kỹ thuật (0-100)</th>
                  <th className="py-2.5 px-4">Đề xuất hành động</th>
                  <th className="py-2.5 px-4 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {filteredItems.map((item) => {
                  const scoreColor = getScoreColor(item.score);
                  const isArchived = item.state === 'ARCHIVED';

                  return (
                    <tr
                      key={item.flag_id}
                      className={cn(
                        'hover:bg-surface-hover/60 transition-colors group',
                        isArchived && 'opacity-60 bg-surface/30'
                      )}
                    >
                      {/* Flag Details */}
                      <td className="py-3 px-4">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-2">
                            <Link
                              to={`/flags/${item.flag_id}`}
                              className="font-medium text-primary hover:text-brand transition-colors flex items-center gap-1"
                            >
                              <span>{item.flag_name}</span>
                              <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </Link>
                            {item.is_temporary && (
                              <span className="px-1.5 py-0.2 rounded-xs text-[10px] font-mono bg-surface-active text-muted border border-border-subtle">
                                Tạm thời
                              </span>
                            )}
                          </div>
                          <span className="text-[11px] font-mono text-muted mt-0.5">{item.flag_key}</span>
                        </div>
                      </td>

                      {/* Lifecycle State */}
                      <td className="py-3 px-3">
                        <FlagHealthBadge state={item.state} />
                      </td>

                      {/* Debt Score & Breakdown */}
                      <td className="py-3 px-3">
                        <div className="flex flex-col gap-1.5">
                          <div className="flex items-center justify-between">
                            <span
                              className={cn(
                                'font-mono font-bold text-xs px-1.5 py-0.5 rounded border',
                                getScoreBorderColor(item.score)
                              )}
                            >
                              {item.score} / 100
                            </span>
                            <span className="text-[10px] text-muted">
                              {item.score < 30 ? 'Khỏe mạnh' : item.score < 60 ? 'Cảnh báo' : 'Nguy cấp'}
                            </span>
                          </div>

                          {/* Progress Bar */}
                          <div className="w-full bg-surface-active rounded-full h-2 overflow-hidden">
                            <div
                              className={cn('h-full transition-all duration-300', scoreColor.split(' ')[1])}
                              style={{ width: `${Math.max(item.score, 4)}%` }}
                            />
                          </div>

                          {/* Micro Breakdown Indicator */}
                          <div className="flex items-center justify-between text-[10px] font-mono text-muted pt-0.5">
                            <span title="Tuổi flag">Tuổi: {item.age_score}</span>
                            <span title="Thời gian rollout 100%">Rollout: {item.rollout_score}</span>
                            <span title="Staleness">Cũ: {item.staleness_score}</span>
                            {item.is_temporary && (
                              <span title="Penalty tạm thời">Tạm: {item.temporary_score}</span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Recommendations */}
                      <td className="py-3 px-4">
                        {item.recommendations.length === 0 ? (
                          <span className="text-muted text-[11px] italic">Không có cảnh báo</span>
                        ) : (
                          <div className="space-y-1">
                            {item.recommendations.map((rec, idx) => (
                              <div
                                key={idx}
                                className="flex items-start gap-1.5 text-[11px] text-secondary leading-tight"
                              >
                                <span className="text-amber-400 shrink-0 mt-0.5">•</span>
                                <span>{rec}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right">
                        {!isArchived ? (
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => setFlagToArchive(item)}
                            className="inline-flex items-center gap-1 text-xs"
                          >
                            <Archive className="w-3.5 h-3.5" />
                            <span>Archive</span>
                          </Button>
                        ) : (
                          <span className="text-[11px] text-muted italic font-mono">Đã lưu trữ</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Archive Confirmation Modal */}
      {flagToArchive && (
        <Modal
          isOpen={true}
          onClose={() => setFlagToArchive(null)}
          title="Xác nhận Archive cờ tính năng"
          description={`Bạn có chắc chắn muốn archive cờ "${flagToArchive.flag_name}" (${flagToArchive.flag_key}) không?`}
        >
          <div className="space-y-4 pt-2">
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-md text-xs text-rose-300 flex items-start gap-2">
              <Info className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
              <div>
                Hành động này sẽ đánh dấu cờ là <strong>ARCHIVED</strong>, ghi nhận vào audit log, và
                khuyến cáo loại bỏ kiểm tra cờ này khỏi mã nguồn ứng dụng để giảm nợ kỹ thuật.
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFlagToArchive(null)}
                disabled={archiveMutation.isPending}
              >
                Hủy bỏ
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => archiveMutation.mutate(flagToArchive.flag_id)}
                disabled={archiveMutation.isPending}
              >
                {archiveMutation.isPending ? 'Đang archive...' : 'Xác nhận Archive'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
