import React from 'react';
import { cn } from '../../lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'danger' | 'warning' | 'info' | 'outline' | 'archived';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className,
  ...props
}) => {
  const variantStyles = {
    default: 'bg-surface-active text-secondary border-border-subtle',
    success: 'bg-status-success-bg text-status-success border-status-success-border',
    danger: 'bg-status-danger-bg text-status-danger border-status-danger-border',
    warning: 'bg-status-warning-bg text-status-warning border-status-warning-border',
    info: 'bg-status-info-bg text-status-info border-status-info-border',
    outline: 'bg-transparent text-secondary border-border-default',
    archived: 'bg-status-archived-bg text-status-archived border-status-archived-border',
  };

  const sizeStyles = {
    sm: 'text-[10px] px-1.5 py-px rounded-xs font-mono leading-4',
    md: 'text-[11px] px-2 py-0.5 rounded-sm font-medium leading-4',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 border select-none whitespace-nowrap',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
