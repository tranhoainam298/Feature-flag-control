import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { changeRequestApi } from '../features/change_requests/api';
import { ChangeRequest, ChangeRequestStatus } from '../types';
import { ChangeRequestDetailModal } from '../features/change_requests/ChangeRequestDetailModal';
import { useApp } from '../context/AppContext';
import {
  GitPullRequest,
  Clock,
  RefreshCw,
  Search,
  ShieldCheck,
  ChevronRight,
} from 'lucide-react';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { SkeletonTable } from '../components/ui/SkeletonTable';

export const ChangeRequestsPage: React.FC = () => {
  const { currentEnvironment, environments, setCurrentEnvironment } = useApp();
  const [statusFilter, setStatusFilter] = useState<ChangeRequestStatus | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCR, setSelectedCR] = useState<ChangeRequest | null>(null);

  const envId = currentEnvironment?.id || (environments.length > 0 ? environments[0].id : '');

  const {
    data: changeRequests = [],
    isLoading,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['change-requests', envId, statusFilter],
    queryFn: () =>
      changeRequestApi.listChangeRequests(
        envId,
        statusFilter !== 'ALL' ? statusFilter : undefined
      ),
    enabled: !!envId,
  });

  const filteredCRs = changeRequests.filter((cr) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      cr.title.toLowerCase().includes(q) ||
      (cr.description && cr.description.toLowerCase().includes(q)) ||
      cr.id.toLowerCase().includes(q)
    );
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPLIED':
        return <Badge variant="success" size="sm">APPLIED</Badge>;
      case 'APPROVED':
        return <Badge variant="default" size="sm">APPROVED</Badge>;
      case 'PENDING':
        return <Badge variant="warning" size="sm">PENDING</Badge>;
      case 'REJECTED':
        return <Badge variant="danger" size="sm">REJECTED</Badge>;
      case 'CANCELLED':
        return <Badge variant="outline" size="sm">CANCELLED</Badge>;
      default:
        return <Badge variant="outline" size="sm">{status}</Badge>;
    }
  };

  const statusTabs: Array<{ id: ChangeRequestStatus | 'ALL'; label: string }> = [
    { id: 'ALL', label: 'All' },
    { id: 'PENDING', label: 'Pending' },
    { id: 'APPROVED', label: 'Approved' },
    { id: 'APPLIED', label: 'Applied' },
    { id: 'REJECTED', label: 'Rejected' },
    { id: 'CANCELLED', label: 'Cancelled' },
  ];

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-primary">
            Change Requests
          </h1>
          <p className="text-[11px] text-muted mt-0.5">
            Four-eyes approval and impact simulation for {currentEnvironment?.name || 'environment'} changes.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={currentEnvironment?.id || ''}
            onChange={(e) => {
              const selected = environments.find((env) => env.id === e.target.value);
              if (selected) setCurrentEnvironment(selected);
            }}
            className="text-xs bg-surface-elevated border border-border-default rounded-sm px-2 py-1.5 text-primary focus:outline-none focus:border-brand cursor-pointer"
          >
            {environments.map((env) => (
              <option key={env.id} value={env.id}>
                {env.name} {env.is_production ? '(Prod)' : ''}
              </option>
            ))}
          </select>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Production Guard Notice */}
      {currentEnvironment?.is_production && (
        <div className="px-3 py-2.5 rounded-sm bg-status-warning-bg border border-status-warning-border flex items-start gap-2.5 text-xs text-status-warning">
          <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block text-status-warning">
              Production environment protected
            </span>
            <span className="text-[11px] text-status-warning/80">
              All flag and targeting changes create a pending Change Request. Creators cannot self-approve (four-eyes principle).
            </span>
          </div>
        </div>
      )}

      {/* Status Tabs & Search */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-0.5">
          {statusTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-2.5 py-1 rounded-sm text-[11px] font-medium whitespace-nowrap transition-colors ${
                statusFilter === tab.id
                  ? 'bg-brand/10 text-brand'
                  : 'text-muted hover:text-secondary hover:bg-surface-hover'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="relative w-52">
          <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by title or ID…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-surface-elevated border border-border-default rounded-sm text-xs text-primary placeholder:text-muted focus:outline-none focus:border-brand"
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border border-border-subtle bg-surface overflow-hidden">
        {isLoading ? (
          <SkeletonTable rows={5} columns={5} />
        ) : filteredCRs.length === 0 ? (
          <div className="px-8 py-12 text-center">
            <div className="text-muted mb-2">
              <GitPullRequest className="w-5 h-5 mx-auto" />
            </div>
            <h3 className="text-xs font-semibold text-primary mb-1">
              No change requests
            </h3>
            <p className="text-[11px] text-muted max-w-xs mx-auto">
              {statusFilter !== 'ALL'
                ? `No requests found with status '${statusFilter}'.`
                : 'No change requests have been created for this environment yet.'}
            </p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-subtle bg-surface-elevated text-[10px] font-mono text-muted uppercase tracking-wider">
                <th className="py-2 px-4 font-medium">Title</th>
                <th className="py-2 px-3 font-medium">Status</th>
                <th className="py-2 px-3 font-medium">Requester</th>
                <th className="py-2 px-3 font-medium">Schedule</th>
                <th className="py-2 px-3 font-medium">Created</th>
                <th className="py-2 px-3 font-medium text-right pr-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle text-xs">
              {filteredCRs.map((cr) => (
                <tr
                  key={cr.id}
                  onClick={() => setSelectedCR(cr)}
                  className="row-hover cursor-pointer group"
                >
                  <td className="py-2.5 px-4">
                    <div className="font-medium text-primary group-hover:text-brand transition-colors">
                      {cr.title}
                    </div>
                    <div className="text-[10px] text-muted font-mono mt-0.5">
                      {cr.id.slice(0, 12)}…
                    </div>
                  </td>
                  <td className="py-2.5 px-3">
                    {getStatusBadge(cr.status)}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-muted text-[11px]">
                    {cr.requested_by.slice(0, 8)}…
                  </td>
                  <td className="py-2.5 px-3 font-mono text-muted text-[11px]">
                    {cr.scheduled_at ? (
                      <span className="flex items-center gap-1 text-status-warning">
                        <Clock className="w-3 h-3" />
                        {new Date(cr.scheduled_at).toLocaleString()}
                      </span>
                    ) : (
                      <span>Immediate</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-muted text-[11px]">
                    {new Date(cr.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-2.5 px-3 text-right pr-4">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCR(cr);
                      }}
                      className="text-[11px] text-muted hover:text-primary transition-colors inline-flex items-center gap-1"
                    >
                      <span>View</span>
                      <ChevronRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail Modal */}
      <ChangeRequestDetailModal
        changeRequest={selectedCR}
        isOpen={!!selectedCR}
        onClose={() => setSelectedCR(null)}
      />
    </div>
  );
};
