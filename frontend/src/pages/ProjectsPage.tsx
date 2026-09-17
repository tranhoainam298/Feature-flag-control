import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { ProjectCard } from '../features/projects/ProjectCard';
import { CreateProjectModal } from '../features/projects/CreateProjectModal';
import { Button } from '../components/ui/Button';
import { Plus, FolderGit2 } from 'lucide-react';
import { EmptyState } from '../components/ui/EmptyState';

export const ProjectsPage: React.FC = () => {
  const { projects, currentOrg, refetchUserAndOrgs } = useApp();
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-primary">Projects</h1>
          <p className="text-xs text-secondary mt-1">
            Manage projects and environments for{' '}
            <span className="text-primary font-medium">{currentOrg?.name || 'Organization'}</span>.
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsCreateOpen(true)}
          leftIcon={<Plus className="w-4 h-4" />}
        >
          New Project
        </Button>
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon={<FolderGit2 className="w-6 h-6" />}
          title="No projects found"
          description="Create your first project to start creating feature flags and managing configuration."
          action={
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsCreateOpen(true)}
              leftIcon={<Plus className="w-4 h-4" />}
            >
              Create Project
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((proj) => (
            <ProjectCard key={proj.id} project={proj} />
          ))}
        </div>
      )}

      <CreateProjectModal
        isOpen={isCreateOpen}
        onClose={() => {
          setIsCreateOpen(false);
          refetchUserAndOrgs();
        }}
      />
    </div>
  );
};
