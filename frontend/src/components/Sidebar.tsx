import React from 'react';
import { NavLink } from 'react-router-dom';
import { Flag, FolderGit2, Users, Sliders, ScrollText, HeartPulse, GitPullRequest, Shield } from 'lucide-react';
import { cn } from '../lib/utils';

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { to: '/flags', label: 'Feature Flags', icon: Flag },
  { to: '/change-requests', label: 'Change Requests', icon: GitPullRequest },
  { to: '/health', label: 'Flag Health', icon: HeartPulse },
  { to: '/segments', label: 'Segments', icon: Users },
  { to: '/config', label: 'Config Center', icon: Sliders },
  { to: '/audit', label: 'Audit Log', icon: ScrollText },
  { to: '/projects', label: 'Projects', icon: FolderGit2 },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-56 border-r border-border-subtle bg-surface flex flex-col shrink-0 h-screen sticky top-0 z-40 select-none">
      {/* Brand */}
      <div className="h-12 px-4 border-b border-border-subtle flex items-center gap-2">
        <div className="w-6 h-6 rounded-sm bg-brand/12 border border-brand/20 flex items-center justify-center">
          <Shield className="w-3.5 h-3.5 text-brand" />
        </div>
        <span className="font-semibold text-sm tracking-tight text-primary">FlagOps</span>
        <span className="ml-auto text-[10px] font-mono text-muted">v1.0</span>
      </div>

      {/* Nav */}
      <nav className="p-2 flex-1 flex flex-col gap-0.5 overflow-y-auto">
        <div className="px-2.5 py-1.5 text-[10px] font-medium tracking-widest text-muted uppercase">
          Management
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 px-2.5 py-1.5 rounded-sm text-xs font-medium transition-colors',
                  isActive
                    ? 'bg-brand/10 text-brand'
                    : 'text-secondary hover:text-primary hover:bg-surface-hover'
                )
              }
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-border-subtle">
        <div className="flex items-center justify-between text-[10px] text-muted font-mono">
          <span>Engine v1.0</span>
          <span className="inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-brand" />
            Online
          </span>
        </div>
      </div>
    </aside>
  );
};
