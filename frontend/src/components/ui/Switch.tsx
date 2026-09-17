import React from 'react';
import { cn } from '../../lib/utils';
import { Loader2 } from 'lucide-react';

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  isLoading?: boolean;
  ariaLabel: string;
  size?: 'sm' | 'md';
  className?: string;
}

export const Switch: React.FC<SwitchProps> = ({
  checked,
  onChange,
  disabled = false,
  isLoading = false,
  ariaLabel,
  size = 'md',
  className,
}) => {
  const isSm = size === 'sm';

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled && !isLoading) {
      onChange(!checked);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled && !isLoading) {
        onChange(!checked);
      }
    }
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled || isLoading}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        'relative inline-flex shrink-0 items-center transition-colors duration-200 ease-in-out cursor-pointer rounded-full border',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        isSm ? 'h-5 w-9' : 'h-6 w-11',
        checked
          ? 'bg-flag-on border-flag-on-border'
          : 'bg-surface-active border-border-default hover:border-border-strong',
        className
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-flex items-center justify-center rounded-full bg-white shadow-md transform transition-transform duration-200 ease-in-out',
          isSm ? 'h-3.5 w-3.5' : 'h-4.5 w-4.5',
          checked
            ? isSm
              ? 'translate-x-4.5'
              : 'translate-x-5.5'
            : 'translate-x-0.5'
        )}
      >
        {isLoading && (
          <Loader2 className={cn('animate-spin text-zinc-700', isSm ? 'w-2.5 h-2.5' : 'w-3 h-3')} />
        )}
      </span>
    </button>
  );
};
