import React from 'react';
import { LifecycleState } from '../../types';
import { cn } from '../../lib/utils';
import { CircleDot, PlayCircle, CheckCircle2, AlertTriangle, Archive } from 'lucide-react';

interface FlagHealthBadgeProps {
  state: LifecycleState;
  score?: number;
  showScore?: boolean;
  className?: string;
}

export const FlagHealthBadge: React.FC<FlagHealthBadgeProps> = ({
  state,
  score,
  showScore = false,
  className,
}) => {
  const getBadgeConfig = (s: LifecycleState) => {
    switch (s) {
      case 'DRAFT':
        return {
          variant: 'outline' as const,
          label: 'DRAFT',
          icon: CircleDot,
          colorClass: 'text-muted border-border-default bg-surface-subtle',
        };
      case 'ACTIVE':
        return {
          variant: 'success' as const,
          label: 'ACTIVE',
          icon: PlayCircle,
          colorClass: 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10',
        };
      case 'ROLLED_OUT':
        return {
          variant: 'info' as const,
          label: 'ROLLED OUT',
          icon: CheckCircle2,
          colorClass: 'text-sky-400 border-sky-500/20 bg-sky-500/10',
        };
      case 'STALE':
        return {
          variant: 'warning' as const,
          label: 'STALE',
          icon: AlertTriangle,
          colorClass: 'text-amber-400 border-amber-500/20 bg-amber-500/10',
        };
      case 'ARCHIVED':
        return {
          variant: 'danger' as const,
          label: 'ARCHIVED',
          icon: Archive,
          colorClass: 'text-rose-400 border-rose-500/20 bg-rose-500/10 opacity-75',
        };
      default:
        return {
          variant: 'default' as const,
          label: s,
          icon: CircleDot,
          colorClass: 'text-secondary border-border-subtle bg-surface',
        };
    }
  };

  const config = getBadgeConfig(state);
  const Icon = config.icon;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-xs font-mono font-medium border select-none',
        config.colorClass,
        className
      )}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      <span>{config.label}</span>
      {showScore && score !== undefined && (
        <span className="ml-1 px-1 rounded text-[10px] bg-surface-active font-mono">
          {score}
        </span>
      )}
    </span>
  );
};
