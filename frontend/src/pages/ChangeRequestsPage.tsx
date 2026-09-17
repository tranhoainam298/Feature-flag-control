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
        return <Badge variant="success">APPLIED</Badge>;
      case 'APPROVED':
        return <Badge variant="default">APPROVED</Badge>;
      case 'PENDING':
        return <Badge variant="warning">PENDING</Badge>;
      case 'REJECTED':
        return <Badge variant="danger">REJECTED</Badge>;
      case 'CANCELLED':
        return <Badge variant="outline">CANCELLED</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const statusTabs: Array<{ id: ChangeRequestStatus | 'ALL'; label: string }> = [
    { id: 'ALL', label: 'Tất cả' },
    { id: 'PENDING', label: 'Chờ duyệt (Pending)' },
    { id: 'APPROVED', label: 'Đã duyệt (Approved)' },
    { id: 'APPLIED', label: 'Đã áp dụng (Applied)' },
    { id: 'REJECTED', label: 'Từ chối (Rejected)' },
    { id: 'CANCELLED', label: 'Đã hủy (Cancelled)' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-primary">
              Quản lý Change Request
            </h1>
            <Badge variant="outline" className="font-mono text-xs">
              Môi trường: {currentEnvironment?.name || 'Chưa chọn'}
              {currentEnvironment?.is_production && ' (Production)'}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-secondary">
            Kiểm soát thay đổi cho môi trường Production theo nguyên tắc bốn mắt (Four-Eyes Principle) và mô phỏng tác động (Impact Simulation).
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Environment Selector */}
          <select
            value={currentEnvironment?.id || ''}
            onChange={(e) => {
              const selected = environments.find((env) => env.id === e.target.value);
              if (selected) setCurrentEnvironment(selected);
            }}
            className="text-xs bg-surface border border-border-default rounded-md px-3 py-1.5 text-primary focus:outline-none focus:border-brand"
          >
            {environments.map((env) => (
              <option key={env.id} value={env.id}>
                {env.name} {env.is_production ? '🛡️ (Prod)' : ''}
              </option>
            ))}
          </select>

          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Làm mới</span>
          </Button>
        </div>
      </div>

      {/* Production Notice Banner */}
      {currentEnvironment?.is_production && (
        <div className="p-3.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-start gap-3 text-xs text-indigo-300">
          <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block text-indigo-200">
              Môi trường Production đang được bảo vệ
            </span>
            <span>
              Mọi thay đổi cờ tính năng hoặc quy tắc targeting sẽ không áp dụng ngay mà tự động tạo Change Request ở trạng thái PENDING. Người tạo không được phép tự duyệt (Nguyên tắc bốn mắt).
            </span>
          </div>
        </div>
      )}

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Status Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
          {statusTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                statusFilter === tab.id
                  ? 'bg-brand/10 text-brand border border-brand/20'
                  : 'text-secondary hover:text-primary hover:bg-surface-hover'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-muted absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Tìm theo tiêu đề hoặc ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-surface border border-border-default rounded-md text-xs text-primary placeholder:text-muted focus:outline-none focus:border-brand"
          />
        </div>
      </div>

      {/* Change Requests Table */}
      <div className="rounded-lg border border-border-default bg-surface overflow-hidden shadow-xs">
        {isLoading ? (
          <div className="p-6">
            <SkeletonTable rows={5} columns={5} />
          </div>
        ) : filteredCRs.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-10 h-10 rounded-full bg-surface-hover flex items-center justify-center text-muted mx-auto mb-3">
              <GitPullRequest className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-primary mb-1">
              Không có Change Request nào
            </h3>
            <p className="text-xs text-muted max-w-sm mx-auto">
              {statusFilter !== 'ALL'
                ? `Không tìm thấy yêu cầu nào ở trạng thái '${statusFilter}'.`
                : 'Chưa có yêu cầu thay đổi nào được tạo trong môi trường này.'}
            </p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-subtle bg-canvas text-[11px] font-semibold text-muted uppercase tracking-wider">
                <th className="py-3 px-4">Tiêu đề Change Request</th>
                <th className="py-3 px-4">Trạng thái</th>
                <th className="py-3 px-4">Người yêu cầu</th>
                <th className="py-3 px-4">Hẹn giờ áp dụng</th>
                <th className="py-3 px-4">Ngày tạo</th>
                <th className="py-3 px-4 text-right">Chi tiết</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle text-xs">
              {filteredCRs.map((cr) => (
                <tr
                  key={cr.id}
                  onClick={() => setSelectedCR(cr)}
                  className="hover:bg-surface-hover/80 transition-colors cursor-pointer group"
                >
                  <td className="py-3 px-4">
                    <div className="font-semibold text-primary group-hover:text-brand transition-colors">
                      {cr.title}
                    </div>
                    <div className="text-[11px] text-muted font-mono truncate max-w-xs mt-0.5">
                      ID: {cr.id.slice(0, 13)}...
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    {getStatusBadge(cr.status)}
                  </td>
                  <td className="py-3 px-4 font-mono text-secondary">
                    {cr.requested_by.slice(0, 8)}...
                  </td>
                  <td className="py-3 px-4 font-mono text-secondary">
                    {cr.scheduled_at ? (
                      <span className="flex items-center gap-1.5 text-amber-400">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(cr.scheduled_at).toLocaleString()}</span>
                      </span>
                    ) : (
                      <span className="text-muted">Tức thì</span>
                    )}
                  </td>
                  <td className="py-3 px-4 font-mono text-muted">
                    {new Date(cr.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCR(cr);
                      }}
                      className="gap-1 text-xs"
                    >
                      <span>Xem & Mô phỏng</span>
                      <ChevronRight className="w-3.5 h-3.5 text-muted group-hover:translate-x-0.5 transition-transform" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Change Request Detail Modal */}
      <ChangeRequestDetailModal
        changeRequest={selectedCR}
        isOpen={!!selectedCR}
        onClose={() => setSelectedCR(null)}
      />
    </div>
  );
};
