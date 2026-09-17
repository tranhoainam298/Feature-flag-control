import React from 'react';
import { NavLink } from 'react-router-dom';
import { Flag, FolderGit2, Users, Sliders, ScrollText, Sparkles, HeartPulse, GitPullRequest } from 'lucide-react';
import { cn } from '../lib/utils';
import { Badge } from './ui/Badge';

export const Sidebar: React.FC = () => {
  interface NavItem {
    to: string;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    exact?: boolean;
    disabled?: boolean;
    tag?: string;
  }

  const navItems: NavItem[] = [
    { to: '/flags', label: 'Feature Flags', icon: Flag, exact: false },
    { to: '/change-requests', label: 'Change Requests', icon: GitPullRequest, exact: false },
    { to: '/health', label: 'Flag Health & Debt', icon: HeartPulse, exact: false },
    { to: '/projects', label: 'Projects & Envs', icon: FolderGit2, exact: true },
    { to: '/segments', label: 'Segments', icon: Users, exact: false },
    { to: '/config', label: 'Config Center', icon: Sliders, exact: false },
    { to: '/audit', label: 'Audit Logs', icon: ScrollText, exact: false },
  ];

  return (
    <aside className="w-60 border-r border-border-subtle bg-surface flex flex-col shrink-0 h-screen sticky top-0 z-40 select-none">
      {/* Brand Header */}
      <div className="h-14 px-5 border-b border-border-subtle flex items-center gap-2.5">
        <div className="w-6 h-6 rounded-md bg-brand flex items-center justify-center text-white shadow-sm shadow-brand/30">
          <Sparkles className="w-3.5 h-3.5" />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="font-semibold text-base tracking-tight text-primary">FlagOps</span>
          <Badge variant="outline" size="sm" className="font-mono text-[10px]">
            v1.0
          </Badge>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="p-3 flex-1 flex flex-col gap-1 overflow-y-auto">
        <div className="px-2 py-1.5 text-[10px] font-semibold tracking-wider text-muted uppercase">
          Management
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          if (item.disabled) {
            return (
              <div
                key={item.label}
                className="flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium text-muted/60 cursor-not-allowed"
                title="Available in Slice 13B / Next"
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4 text-muted/50" />
                  <span>{item.label}</span>
                </div>
                {item.tag && (
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-xs bg-surface-hover text-muted">
                    {item.tag}
                  </span>
                )}
              </div>
            );
          }

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors',
                  isActive
                    ? 'bg-brand/10 text-brand border border-brand/20'
                    : 'text-secondary hover:text-primary hover:bg-surface-hover'
                )
              }
            >
              <div className="flex items-center gap-2.5">
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </div>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-border-subtle bg-surface/50">
        <div className="flex items-center justify-between text-[11px] text-muted font-mono">
          <span>Engine: Pure (v1.0)</span>
          <span className="inline-block w-2 h-2 rounded-full bg-flag-on animate-pulse" />
        </div>
      </div>
    </aside>
  );
};
