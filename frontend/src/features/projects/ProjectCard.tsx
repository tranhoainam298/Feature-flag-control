import React from 'react';
import { Link } from 'react-router-dom';
import { Project } from '../../types';
import { FolderGit2, ArrowRight, Flag } from 'lucide-react';
import { Badge } from '../../components/ui/Badge';
import { useApp } from '../../context/AppContext';

export const ProjectCard: React.FC<{ project: Project }> = ({ project }) => {
  const { currentProject, setCurrentProject } = useApp();
  const isSelected = currentProject?.id === project.id;

  return (
    <div className="bg-surface border border-border-default hover:border-border-strong rounded-lg p-5 transition-all flex flex-col justify-between group">
      <div>
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-md bg-surface-elevated text-brand border border-border-subtle">
              <FolderGit2 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-primary group-hover:text-brand transition-colors">
                {project.name}
              </h3>
              <span className="font-mono text-xs text-muted">key: {project.key}</span>
            </div>
          </div>
          {isSelected && (
            <Badge variant="success" size="sm">
              ACTIVE
            </Badge>
          )}
        </div>

        <p className="text-xs text-secondary line-clamp-2 mt-2 mb-4">
          {project.description || 'No description provided for this project.'}
        </p>
      </div>

      <div className="pt-4 border-t border-border-subtle flex items-center justify-between text-xs">
        <button
          type="button"
          onClick={() => setCurrentProject(project)}
          className="text-xs text-secondary hover:text-primary font-medium flex items-center gap-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand rounded-xs"
        >
          <span>Select Project</span>
        </button>

        <div className="flex items-center gap-3">
          <Link
            to={`/projects/${project.id}`}
            className="text-xs text-muted hover:text-primary flex items-center gap-1"
          >
            <span>Overview</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
          <Link
            to="/flags"
            onClick={() => setCurrentProject(project)}
            className="text-xs text-brand hover:underline font-medium flex items-center gap-1"
          >
            <Flag className="w-3 h-3" />
            <span>View Flags</span>
          </Link>
        </div>
      </div>
    </div>
  );
};
