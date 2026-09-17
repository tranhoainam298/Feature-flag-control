import React from 'react';
import { useApp } from '../context/AppContext';
import { FolderGit2, Layers, LogOut, ChevronDown } from 'lucide-react';
import { Badge } from './ui/Badge';

export const Topbar: React.FC = () => {
  const {
    user,
    currentOrg,
    projects,
    currentProject,
    setCurrentProject,
    environments,
    currentEnvironment,
    setCurrentEnvironment,
    logout,
  } = useApp();

  return (
    <header className="h-11 border-b border-border-subtle bg-surface/90 backdrop-blur-sm px-4 flex items-center justify-between sticky top-0 z-30">
      {/* Context Selectors */}
      <div className="flex items-center gap-3 text-xs">
        {/* Project */}
        <div className="flex items-center gap-1.5">
          <FolderGit2 className="w-3.5 h-3.5 text-muted shrink-0" />
          <label htmlFor="topbar-project" className="sr-only">Project</label>
          <div className="relative">
            <select
              id="topbar-project"
              value={currentProject?.id || ''}
              onChange={(e) => {
                const proj = projects.find((p) => p.id === e.target.value);
                if (proj) setCurrentProject(proj);
              }}
              className="appearance-none bg-transparent text-primary text-xs font-medium pl-0 pr-5 py-1 border-none focus-visible:outline-none cursor-pointer"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3 h-3 text-muted absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        <span className="text-border-strong text-muted">/</span>

        {/* Environment */}
        <div className="flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-muted shrink-0" />
          <label htmlFor="topbar-env" className="sr-only">Environment</label>
          <div className="relative">
            <select
              id="topbar-env"
              value={currentEnvironment?.id || ''}
              onChange={(e) => {
                const env = environments.find((ev) => ev.id === e.target.value);
                if (env) setCurrentEnvironment(env);
              }}
              className="appearance-none bg-transparent text-primary text-xs font-medium pl-0 pr-5 py-1 border-none focus-visible:outline-none cursor-pointer"
            >
              {environments.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  {ev.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3 h-3 text-muted absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
          {currentEnvironment?.is_production && (
            <Badge variant="warning" size="sm">PROD</Badge>
          )}
        </div>
      </div>

      {/* User & Org */}
      <div className="flex items-center gap-2.5">
        {currentOrg && (
          <span className="hidden sm:inline text-[10px] font-mono text-muted uppercase tracking-wider">
            {currentOrg.name}
          </span>
        )}
        <div className="flex items-center gap-2 pl-2.5 border-l border-border-subtle">
          <div className="w-6 h-6 rounded-sm bg-surface-elevated border border-border-default flex items-center justify-center text-[10px] font-semibold text-secondary">
            {user?.email?.[0].toUpperCase() || 'U'}
          </div>
          <div className="hidden md:flex flex-col">
            <span className="text-[11px] font-medium text-primary leading-tight">
              {user?.full_name || user?.email}
            </span>
          </div>
          <button
            onClick={logout}
            aria-label="Sign out"
            title="Sign out"
            className="p-1 text-muted hover:text-status-danger rounded-sm transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  );
};
