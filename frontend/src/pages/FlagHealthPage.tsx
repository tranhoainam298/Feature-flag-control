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
import { TechnicalDebtGauge } from '../components/TechnicalDebtGauge';

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

  const getScoreBorderColor = (score: number) => {
    if (score < 30) return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400';
    if (score < 60) return 'border-amber-500/20 bg-amber-500/10 text-amber-400';
    return 'border-rose-500/20 bg-rose-500/10 text-rose-400';
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border-default pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-semibold tracking-tight text-primary">Flag Lifecycle & Health</h1>
            <span className="px-1.5 py-0.5 rounded-xs text-[10px] font-mono font-medium bg-brand/10 text-brand border border-brand/20">
              AUDIT ENGINE
            </span>
          </div>
          <p className="text-xs text-secondary mt-0.5">
            Monitor technical debt scores, lifecycle state transitions, and cleanup recommendations for{' '}
            <span className="text-primary font-medium">{currentProject?.name || 'Project'}</span>.
          </p>
        </div>
      </div>

      {/* Summary KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
          <div className="p-3 rounded-md bg-surface border border-border-default flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-secondary" /> Total Flags
            </span>
            <span className="text-lg font-bold font-mono text-primary mt-1.5">{summary.total}</span>
          </div>

          <div className="p-3 rounded-md bg-surface border border-border-default flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <CircleDot className="w-3.5 h-3.5 text-muted" /> Draft
            </span>
            <span className="text-lg font-bold font-mono text-secondary mt-1.5">{summary.draft_count}</span>
          </div>

          <div className="p-3 rounded-md bg-surface border border-border-default flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <PlayCircle className="w-3.5 h-3.5 text-emerald-400" /> Active
            </span>
            <span className="text-lg font-bold font-mono text-emerald-400 mt-1.5">{summary.active_count}</span>
          </div>

          <div className="p-3 rounded-md bg-surface border border-border-default flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" /> Rolled Out
            </span>
            <span className="text-lg font-bold font-mono text-sky-400 mt-1.5">{summary.rolled_out_count}</span>
          </div>

          <div className="p-3 rounded-md bg-surface border border-status-warning/30 bg-status-warning/5 flex flex-col justify-between">
            <span className="text-[11px] text-status-warning font-medium flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-status-warning" /> Stale (Action Needed)
            </span>
            <span className="text-lg font-bold font-mono text-status-warning mt-1.5">{summary.stale_count}</span>
          </div>

          <div className="p-3 rounded-md bg-surface border border-border-default flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <Archive className="w-3.5 h-3.5 text-muted" /> Archived
            </span>
            <span className="text-lg font-bold font-mono text-muted mt-1.5">{summary.archived_count}</span>
          </div>

          <div className="p-3 rounded-md bg-surface border border-border-default flex flex-col justify-between">
            <span className="text-[11px] text-muted font-medium flex items-center gap-1.5">
              <HeartPulse className="w-3.5 h-3.5 text-brand" /> Avg Debt Score
            </span>
            <div className="flex items-center justify-between mt-1.5">
              <TechnicalDebtGauge score={summary.avg_score} size="sm" />
              <span className="text-[10px] text-muted font-mono">
                {summary.avg_score < 30 ? 'Healthy' : summary.avg_score <= 60 ? 'Warning' : 'Critical'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-surface p-2.5 rounded-md border border-border-default">
        {/* Search Input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="Search by flag name or key..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface-elevated border border-border-default rounded-xs text-primary placeholder:text-muted focus:outline-hidden focus:border-brand transition-colors"
          />
        </div>

        {/* Filters Group */}
        <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto">
          {/* State Filter */}
          <div className="flex items-center gap-1 text-xs text-secondary">
            <SlidersHorizontal className="w-3.5 h-3.5 text-muted shrink-0" />
            <select
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              className="bg-surface-elevated border border-border-default rounded-xs px-2 py-1 text-xs text-primary focus:outline-hidden focus:border-brand"
            >
              <option value="ALL">All States</option>
              <option value="DRAFT">DRAFT</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="ROLLED_OUT">ROLLED OUT</option>
              <option value="STALE">STALE (Deprecate)</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>
          </div>

          {/* Min Score Filter */}
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="bg-surface-elevated border border-border-default rounded-xs px-2 py-1 text-xs text-primary focus:outline-hidden focus:border-brand"
          >
            <option value="0">All Debt Scores</option>
            <option value="30">Debt Score ≥ 30 (Moderate & High)</option>
            <option value="60">Debt Score ≥ 60 (High)</option>
          </select>

          {/* Sort By */}
          <div className="flex items-center gap-1 text-xs text-secondary">
            <ArrowUpDown className="w-3.5 h-3.5 text-muted shrink-0" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-surface-elevated border border-border-default rounded-xs px-2 py-1 text-xs text-primary focus:outline-hidden focus:border-brand"
            >
              <option value="score">Sort: Highest Debt Score</option>
              <option value="name">Sort: Flag Name A-Z</option>
              <option value="state">Sort: Lifecycle State</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <SkeletonTable rows={5} columns={5} />
      ) : isError ? (
        <ErrorAlert
          title="Failed to load flag health metrics"
          error={error}
          onRetry={() => refetch()}
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={<HeartPulse className="w-6 h-6 text-muted" />}
          title="No feature flags match criteria"
          description="No feature flags match the selected filters or search query."
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
              Reset Filters
            </Button>
          }
        />
      ) : (
        <div className="border border-border-default rounded-md overflow-hidden bg-surface">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border-default bg-surface-elevated/40 text-secondary font-medium uppercase tracking-wider text-[10px]">
                  <th className="py-2.5 px-3">Flag / Identifier</th>
                  <th className="py-2.5 px-3">Lifecycle State</th>
                  <th className="py-2.5 px-3 w-52">Technical Debt Score (0-100)</th>
                  <th className="py-2.5 px-3">Recommendations</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {filteredItems.map((item) => {
                  const isArchived = item.state === 'ARCHIVED';

                  return (
                    <tr
                      key={item.flag_id}
                      className={cn(
                        'hover:bg-surface-elevated/50 transition-colors group',
                        isArchived && 'opacity-60 bg-surface/30'
                      )}
                    >
                      {/* Flag Details */}
                      <td className="py-2.5 px-3">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1.5">
                            <Link
                              to={`/flags/${item.flag_id}`}
                              className="font-medium text-primary hover:text-brand transition-colors flex items-center gap-1"
                            >
                              <span>{item.flag_name}</span>
                              <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity text-muted" />
                            </Link>
                            {item.is_temporary && (
                              <span className="px-1.5 py-0.2 rounded-xs text-[10px] font-mono bg-surface-elevated text-muted border border-border-subtle">
                                Temporary
                              </span>
                            )}
                          </div>
                          <span className="text-[11px] font-mono text-muted mt-0.5">{item.flag_key}</span>
                        </div>
                      </td>

                      {/* Lifecycle State */}
                      <td className="py-2.5 px-3">
                        <FlagHealthBadge state={item.state} />
                      </td>

                      {/* Debt Score & Breakdown */}
                      <td className="py-2.5 px-3">
                        <div className="flex items-center gap-2.5">
                          <TechnicalDebtGauge score={item.score} size="sm" />
                          <div className="flex-1 flex flex-col gap-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span
                                className={cn(
                                  'font-mono font-bold text-[11px] px-1.5 py-0.2 rounded-xs border',
                                  getScoreBorderColor(item.score)
                                )}
                              >
                                {item.score} / 100
                              </span>
                              <span className="text-[10px] text-muted">
                                {item.score < 30 ? 'Healthy' : item.score <= 60 ? 'Warning' : 'Critical'}
                              </span>
                            </div>

                            {/* Micro Breakdown Indicator */}
                            <div className="flex items-center justify-between text-[9px] font-mono text-muted pt-0.5">
                              <span title="Flag age score">Age: {item.age_score}</span>
                              <span title="Full rollout score">Rollout: {item.rollout_score}</span>
                              <span title="Staleness score">Stale: {item.staleness_score}</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Recommendations */}
                      <td className="py-2.5 px-3">
                        {item.recommendations.length === 0 ? (
                          <span className="text-muted text-[11px] italic">No active warnings</span>
                        ) : (
                          <div className="space-y-0.5">
                            {item.recommendations.map((rec, idx) => (
                              <div
                                key={idx}
                                className="flex items-start gap-1.5 text-[11px] text-secondary leading-tight"
                              >
                                <span className="text-status-warning shrink-0 mt-0.5">•</span>
                                <span>{rec}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-2.5 px-3 text-right">
                        {!isArchived ? (
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => setFlagToArchive(item)}
                            className="inline-flex items-center gap-1 text-xs h-7 px-2.5"
                          >
                            <Archive className="w-3 h-3" />
                            <span>Archive</span>
                          </Button>
                        ) : (
                          <span className="text-[11px] text-muted italic font-mono">Archived</span>
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
          title="Confirm Archive Feature Flag"
          description={`Are you sure you want to archive "${flagToArchive.flag_name}" (${flagToArchive.flag_key})?`}
        >
          <div className="space-y-3.5 pt-2">
            <div className="p-3 bg-status-danger/10 border border-status-danger/20 rounded-xs text-xs text-status-danger flex items-start gap-2">
              <Info className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                Archiving this flag sets its lifecycle state to <strong>ARCHIVED</strong>, records an audit event,
                and recommends removing the flag check from application source code to eliminate technical debt.
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border-subtle">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFlagToArchive(null)}
                disabled={archiveMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => archiveMutation.mutate(flagToArchive.flag_id)}
                disabled={archiveMutation.isPending}
              >
                {archiveMutation.isPending ? 'Archiving...' : 'Confirm Archive'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
