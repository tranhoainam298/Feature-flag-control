import React from 'react';
import { useTheme, ThemeMode } from '../context/ThemeContext';
import { Sun, Moon, Monitor } from 'lucide-react';

export const ThemeToggle: React.FC = () => {
  const { theme, setTheme } = useTheme();

  const options: { mode: ThemeMode; label: string; icon: React.ReactNode }[] = [
    { mode: 'light', label: 'Light theme', icon: <Sun className="w-3 h-3" /> },
    { mode: 'system', label: 'System theme', icon: <Monitor className="w-3 h-3" /> },
    { mode: 'dark', label: 'Dark theme', icon: <Moon className="w-3 h-3" /> },
  ];

  return (
    <div
      role="radiogroup"
      aria-label="Theme selection"
      className="inline-flex items-center p-0.5 rounded-sm bg-surface-elevated border border-border-default transition-colors duration-200"
    >
      {options.map((opt) => {
        const isSelected = theme === opt.mode;
        return (
          <button
            key={opt.mode}
            role="radio"
            aria-checked={isSelected}
            aria-label={opt.label}
            title={opt.label}
            onClick={() => setTheme(opt.mode)}
            className={`flex items-center justify-center p-1 rounded-xs text-xs transition-all duration-200 ${
              isSelected
                ? 'bg-surface text-primary shadow-sm border border-border-subtle'
                : 'text-muted hover:text-primary hover:bg-surface-hover border border-transparent'
            }`}
          >
            {opt.icon}
          </button>
        );
      })}
    </div>
  );
};
