import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './Button';

interface Props {
  error: unknown;
  title?: string;
  onRetry?: () => void;
}

export const ErrorAlert: React.FC<Props> = ({ error, title, onRetry }) => {
  const message = error instanceof Error
    ? error.message
    : typeof error === 'string'
    ? error
    : 'An unexpected error occurred.';

  return (
    <div className="border border-status-danger-border rounded-sm bg-status-danger-bg px-4 py-3 flex items-start gap-3">
      <AlertTriangle className="w-4 h-4 text-status-danger shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-status-danger">
          {title || 'Error'}
        </p>
        <p className="text-[11px] text-status-danger/80 mt-0.5 font-mono">{message}</p>
      </div>
      {onRetry && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onRetry}
          leftIcon={<RefreshCw className="w-3 h-3" />}
          className="text-status-danger hover:text-status-danger shrink-0"
        >
          Retry
        </Button>
      )}
    </div>
  );
};
