import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';
import { Button } from './Button';

export interface ErrorAlertProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  error,
  onRetry,
  title = 'Failed to load data',
}) => {
  let message = 'An unexpected error occurred';
  if (typeof error === 'string') {
    message = error;
  } else if (error && typeof error === 'object') {
    if ('message' in error && typeof (error as { message: unknown }).message === 'string') {
      message = (error as { message: string }).message;
    }
  }

  return (
    <div
      role="alert"
      className="flex items-start gap-3.5 p-4 rounded-md bg-status-danger/10 border border-status-danger/30 text-primary my-4"
    >
      <AlertCircle className="w-5 h-5 text-status-danger shrink-0 mt-0.5" />
      <div className="flex-1">
        <h4 className="text-sm font-semibold text-status-danger">{title}</h4>
        <p className="text-xs text-secondary mt-1">{message}</p>
        {onRetry && (
          <div className="mt-3">
            <Button
              size="sm"
              variant="outline"
              onClick={onRetry}
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            >
              Retry
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
