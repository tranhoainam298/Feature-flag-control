import React from 'react';
import { cn } from '../../lib/utils';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'secondary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const variantStyles = {
      primary:
        'bg-brand hover:bg-brand-hover text-white border border-brand/40 active:scale-[0.98]',
      secondary:
        'bg-surface-elevated hover:bg-surface-hover text-primary border border-border-default active:scale-[0.98]',
      danger:
        'bg-status-danger hover:brightness-110 text-white border border-status-danger/40 active:scale-[0.98]',
      ghost:
        'bg-transparent hover:bg-surface-hover text-secondary hover:text-primary border border-transparent',
      outline:
        'bg-transparent hover:bg-surface-hover text-secondary hover:text-primary border border-border-default active:scale-[0.98]',
    };

    const sizeStyles = {
      sm: 'text-xs px-2.5 py-1 rounded-sm gap-1.5 h-7',
      md: 'text-xs px-3 py-1.5 rounded-sm gap-2 h-8',
      lg: 'text-sm px-4 py-2 rounded-md gap-2 h-9',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-all duration-100',
          'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand',
          'disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none select-none',
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-current" />
        ) : (
          leftIcon && <span className="inline-flex shrink-0">{leftIcon}</span>
        )}
        <span>{children}</span>
        {!isLoading && rightIcon && <span className="inline-flex shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';
