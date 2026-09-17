import React from 'react';
import { cn } from '../lib/utils';

interface TechnicalDebtGaugeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

export const TechnicalDebtGauge: React.FC<TechnicalDebtGaugeProps> = ({
  score,
  size = 'md',
  showLabel = false,
  className,
}) => {
  const clampedScore = Math.max(0, Math.min(100, Math.round(score)));

  // Color mapping according to requirement:
  // Under 30: Emerald (#10b981)
  // 30 - 60: Amber (#f59e0b)
  // Over 60: Rose (#f43f5e)
  const getLevel = () => {
    if (clampedScore < 30) {
      return {
        level: 'Healthy',
        stroke: '#10b981',
        textClass: 'text-emerald-600 dark:text-emerald-400',
        bgClass: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-400',
      };
    }
    if (clampedScore <= 60) {
      return {
        level: 'Warning',
        stroke: '#f59e0b',
        textClass: 'text-amber-600 dark:text-amber-400',
        bgClass: 'bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400',
      };
    }
    return {
      level: 'Critical',
      stroke: '#f43f5e',
      textClass: 'text-rose-600 dark:text-rose-400',
      bgClass: 'bg-rose-500/10 border-rose-500/20 text-rose-600 dark:text-rose-400',
    };
  };

  const { level, stroke, textClass, bgClass } = getLevel();

  const dimensions = {
    sm: { size: 36, strokeWidth: 3.5, radius: 14, fontSize: 'text-[11px]' },
    md: { size: 48, strokeWidth: 4, radius: 19, fontSize: 'text-xs' },
    lg: { size: 64, strokeWidth: 5, radius: 26, fontSize: 'text-sm' },
  }[size];

  const circumference = 2 * Math.PI * dimensions.radius;
  const strokeDashoffset = circumference - (clampedScore / 100) * circumference;

  return (
    <div className={cn('inline-flex items-center gap-2', className)}>
      <div
        className="relative flex items-center justify-center"
        style={{ width: dimensions.size, height: dimensions.size }}
        title={`Technical Debt Score: ${clampedScore} / 100 (${level})`}
      >
        <svg
          width={dimensions.size}
          height={dimensions.size}
          viewBox={`0 0 ${dimensions.size} ${dimensions.size}`}
          className="-rotate-90"
        >
          {/* Background track */}
          <circle
            cx={dimensions.size / 2}
            cy={dimensions.size / 2}
            r={dimensions.radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={dimensions.strokeWidth}
            className="text-surface-active"
          />
          {/* Progress arc */}
          <circle
            cx={dimensions.size / 2}
            cy={dimensions.size / 2}
            r={dimensions.radius}
            fill="none"
            stroke={stroke}
            strokeWidth={dimensions.strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-500 ease-out"
          />
        </svg>

        {/* Center score */}
        <span
          className={cn(
            'absolute font-mono font-bold leading-none select-none',
            dimensions.fontSize,
            textClass
          )}
        >
          {clampedScore}
        </span>
      </div>

      {showLabel && (
        <div className="flex flex-col">
          <span className={cn('px-1.5 py-0.5 rounded-xs text-[10px] font-mono font-semibold border', bgClass)}>
            {level.toUpperCase()}
          </span>
        </div>
      )}
    </div>
  );
};
