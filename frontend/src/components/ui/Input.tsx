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
      <div className="w-full flex flex-col gap-1">
        {label && (
          <label
            htmlFor={inputId}
            className="text-[11px] font-medium text-secondary"
          >
            {label}
            {props.required && <span className="text-status-danger ml-0.5">*</span>}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          className={cn(
            'w-full bg-surface-elevated text-primary text-xs px-3 py-2 rounded-sm border transition-colors',
            'border-border-default placeholder:text-muted',
            'focus:border-brand focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand/50',
            'disabled:opacity-40 disabled:cursor-not-allowed',
            error && 'border-status-danger focus:border-status-danger focus-visible:ring-status-danger/40',
            className
          )}
          {...props}
        />
        {helperText && !error && (
          <p id={helperId} className="text-[10px] text-muted">
            {helperText}
          </p>
        )}
        {error && (
          <p id={errorId} role="alert" className="text-[10px] text-status-danger font-medium">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
