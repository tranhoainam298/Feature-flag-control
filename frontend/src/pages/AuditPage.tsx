import React from 'react';
import { AuditTable } from '../features/audit/AuditTable';

export const AuditPage: React.FC = () => {
  return (
    <div className="space-y-4">
      <div className="border-b border-border-default pb-3">
        <h1 className="text-base font-semibold tracking-tight text-primary">
          Audit Logs
        </h1>
        <p className="mt-0.5 text-xs text-secondary">
          Comprehensive, tamper-evident records of configuration updates, feature flag mutations, rollout releases, and security events with Before / After state snapshots.
        </p>
      </div>

      <AuditTable />
    </div>
  );
};
