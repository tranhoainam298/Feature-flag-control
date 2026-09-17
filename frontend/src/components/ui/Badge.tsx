import React from 'react';
import { cn } from '../../lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'danger' | 'warning' | 'info' | 'outline';
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
    success: 'bg-flag-on-bg text-flag-on border-flag-on-border',
    danger: 'bg-flag-off-bg text-status-danger border-border-subtle',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    info: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
    outline: 'bg-transparent text-secondary border-border-default',
  };

  const sizeStyles = {
    sm: 'text-[11px] px-1.5 py-0.5 rounded-xs font-mono',
    md: 'text-xs px-2 py-0.5 rounded-sm font-medium',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 border font-sans tracking-tight select-none',
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
