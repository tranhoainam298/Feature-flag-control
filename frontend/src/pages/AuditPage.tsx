import React from 'react';
import { AuditTable } from '../features/audit/AuditTable';

export const AuditPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
          Nhật ký Kiểm toán (Audit Logs)
        </h1>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          Theo dõi toàn diện lịch sử thay đổi cấu hình, cờ tính năng, phân phối rollout, bảo mật và so sánh snapshot Before / After.
        </p>
      </div>

      <AuditTable />
    </div>
  );
};
