import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { EnvironmentList } from '../features/projects/EnvironmentList';
import { ArrowLeft, Flag, FolderGit2 } from 'lucide-react';
import { Button } from '../components/ui/Button';

export const ProjectDetailPage: React.FC = () => {
  const { id: projectId } = useParams<{ id: string }>();
  const { projects, setCurrentProject } = useApp();

  const project = projects.find((p) => p.id === projectId);

  if (!project) {
    return (
      <div className="p-8 text-center text-secondary">
        <p>Project not found.</p>
        <Link to="/projects" className="text-brand text-xs hover:underline mt-2 inline-block">
          Return to projects
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/projects"
          className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-primary transition-colors font-medium mb-3"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to projects</span>
        </Link>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-surface-elevated text-brand border border-border-subtle">
              <FolderGit2 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-primary">{project.name}</h1>
              <p className="font-mono text-xs text-muted">Key: {project.key}</p>
            </div>
          </div>
          <Link to="/flags" onClick={() => setCurrentProject(project)}>
            <Button size="sm" variant="primary" leftIcon={<Flag className="w-3.5 h-3.5" />}>
              Manage Flags
            </Button>
          </Link>
        </div>
        {project.description && (
          <p className="text-xs text-secondary mt-3 max-w-2xl">{project.description}</p>
        )}
      </div>

      <div className="pt-4 border-t border-border-subtle">
        <EnvironmentList projectId={project.id} />
      </div>
    </div>
  );
};
