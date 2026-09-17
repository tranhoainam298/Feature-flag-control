import React, { useRef, useEffect } from 'react';
import { Search, Plus, Archive } from 'lucide-react';
import { Button } from '../../components/ui/Button';

interface Props {
  search: string;
  onSearchChange: (search: string) => void;
  typeFilter: string;
  onTypeFilterChange: (type: string) => void;
  showArchived: boolean;
  onToggleArchived: () => void;
  onOpenCreate: () => void;
}

export const FlagFilterBar: React.FC<Props> = ({
  search,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  showArchived,
  onToggleArchived,
  onOpenCreate,
}) => {
  const searchRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut: "/" to focus search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
        const active = document.activeElement;
        if (active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA') return;
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 flex-1">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            ref={searchRef}
            type="text"
            placeholder="Search flags…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-surface-elevated text-primary text-xs pl-8 pr-8 py-1.5 rounded-sm border border-border-default placeholder:text-muted focus:border-brand focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand/50"
            aria-label="Search feature flags"
          />
          <kbd className="absolute right-2 top-1/2 -translate-y-1/2 text-[9px] font-mono text-muted bg-surface-active px-1 py-px rounded-xs border border-border-subtle pointer-events-none">
            /
          </kbd>
        </div>

        {/* Type Filter */}
        <select
          value={typeFilter}
          onChange={(e) => onTypeFilterChange(e.target.value)}
          aria-label="Filter by type"
          className="bg-surface-elevated text-secondary text-xs px-2 py-1.5 rounded-sm border border-border-default focus:border-brand focus-visible:outline-none cursor-pointer"
        >
          <option value="">All Types</option>
          <option value="BOOLEAN">Boolean</option>
          <option value="STRING">String</option>
          <option value="NUMBER">Number</option>
          <option value="JSON">JSON</option>
        </select>

        {/* Archive Toggle */}
        <Button
          type="button"
          variant={showArchived ? 'primary' : 'ghost'}
          size="sm"
          onClick={onToggleArchived}
          leftIcon={<Archive className="w-3 h-3" />}
          aria-label={showArchived ? 'Hide archived' : 'Show archived'}
        >
          {showArchived ? 'Archived' : 'Active'}
        </Button>
      </div>

      <Button
        variant="primary"
        size="sm"
        onClick={onOpenCreate}
        leftIcon={<Plus className="w-3.5 h-3.5" />}
      >
        Create Flag
      </Button>
    </div>
  );
};
