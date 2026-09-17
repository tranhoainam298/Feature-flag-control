import React from 'react';
import { useApp } from '../context/AppContext';
import { FolderGit2, Layers, LogOut, ShieldCheck } from 'lucide-react';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';

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
    <header className="h-14 border-b border-border-subtle bg-surface/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Project and Environment Selectors */}
      <div className="flex items-center gap-4">
        {/* Project Selector */}
        <div className="flex items-center gap-2">
          <FolderGit2 className="w-4 h-4 text-secondary shrink-0" />
          <label htmlFor="topbar-project-select" className="sr-only">
            Select Project
          </label>
          <select
            id="topbar-project-select"
            value={currentProject?.id || ''}
            onChange={(e) => {
              const proj = projects.find((p) => p.id === e.target.value);
              if (proj) setCurrentProject(proj);
            }}
            className="bg-surface-elevated text-primary text-xs font-medium border border-border-default rounded-sm px-2.5 py-1.5 focus:border-brand focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand cursor-pointer"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <span className="text-border-default">/</span>

        {/* Environment Selector */}
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-secondary shrink-0" />
          <label htmlFor="topbar-env-select" className="sr-only">
            Select Environment
          </label>
          <select
            id="topbar-env-select"
            value={currentEnvironment?.id || ''}
            onChange={(e) => {
              const env = environments.find((ev) => ev.id === e.target.value);
              if (env) setCurrentEnvironment(env);
            }}
            className="bg-surface-elevated text-primary text-xs font-medium border border-border-default rounded-sm px-2.5 py-1.5 focus:border-brand focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand cursor-pointer"
          >
            {environments.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.name} {ev.is_production ? '(Prod)' : ''}
              </option>
            ))}
          </select>
          {currentEnvironment?.is_production && (
            <Badge variant="warning" size="sm">
              PROD
            </Badge>
          )}
        </div>
      </div>

      {/* User Info & Organization */}
      <div className="flex items-center gap-3">
        {currentOrg && (
          <Badge variant="outline" size="sm" className="hidden sm:inline-flex">
            {currentOrg.name}
          </Badge>
        )}
        <div className="flex items-center gap-2 pl-3 border-l border-border-subtle">
          <div className="w-7 h-7 rounded-full bg-brand/20 border border-brand/40 flex items-center justify-center text-brand text-xs font-semibold">
            {user?.email?.[0].toUpperCase() || 'U'}
          </div>
          <div className="hidden md:flex flex-col text-left">
            <span className="text-xs font-medium text-primary flex items-center gap-1">
              {user?.full_name || user?.email}
              {user?.is_superuser && (
                <span title="Superuser">
                  <ShieldCheck className="w-3 h-3 text-brand" />
                </span>
              )}
            </span>
            <span className="text-[10px] text-muted">{user?.email}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            aria-label="Log out of FlagOps"
            className="text-muted hover:text-status-danger p-1.5 h-auto ml-1"
            title="Log out"
          >
            <LogOut className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </header>
  );
};
