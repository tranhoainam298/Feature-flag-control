import React from 'react';
import { cn } from '../../lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, id, className, ...props }, ref) => {
    const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);
    const errorId = inputId ? `${inputId}-error` : undefined;
    const helperId = inputId ? `${inputId}-helper` : undefined;

    return (
      <div className="w-full flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-xs font-medium text-secondary uppercase tracking-wider"
          >
            {label}
            {props.required && <span className="text-status-danger ml-1">*</span>}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          className={cn(
            'w-full bg-surface-elevated text-primary text-sm px-3 py-2 rounded-md border transition-colors',
            'border-border-default placeholder:text-muted',
            'focus:border-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            error && 'border-status-danger focus:border-status-danger focus-visible:ring-status-danger/40',
            className
          )}
          {...props}
        />
        {helperText && !error && (
          <p id={helperId} className="text-xs text-muted">
            {helperText}
          </p>
        )}
        {error && (
          <p id={errorId} role="alert" className="text-xs text-status-danger font-medium">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
