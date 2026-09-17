import React from 'react';
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
  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-4">
      <div className="flex items-center gap-2.5 flex-1">
        {/* Search input */}
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search flags by key or name..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-surface-elevated text-primary text-xs pl-9 pr-3 py-2 rounded-md border border-border-default placeholder:text-muted focus:border-brand focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand"
            aria-label="Search feature flags"
          />
        </div>

        {/* Type Filter */}
        <select
          value={typeFilter}
          onChange={(e) => onTypeFilterChange(e.target.value)}
          aria-label="Filter by flag type"
          className="bg-surface-elevated text-secondary text-xs px-2.5 py-2 rounded-md border border-border-default focus:border-brand focus-visible:outline-none cursor-pointer"
        >
          <option value="">All Types</option>
          <option value="BOOLEAN">Boolean</option>
          <option value="STRING">String</option>
          <option value="NUMBER">Number</option>
          <option value="JSON">JSON</option>
        </select>

        {/* Archived toggle */}
        <Button
          type="button"
          variant={showArchived ? 'primary' : 'secondary'}
          size="sm"
          onClick={onToggleArchived}
          leftIcon={<Archive className="w-3.5 h-3.5" />}
          aria-label={showArchived ? 'Hide archived flags' : 'Show archived flags'}
          className="h-8"
        >
          {showArchived ? 'Archived' : 'Active'}
        </Button>
      </div>

      <div>
        <Button
          variant="primary"
          size="sm"
          onClick={onOpenCreate}
          leftIcon={<Plus className="w-4 h-4" />}
          className="h-8"
        >
          Create Flag
        </Button>
      </div>
    </div>
  );
};
