import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { projectApi } from './api';
import { useApp } from '../../context/AppContext';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

const projectSchema = z.object({
  key: z
    .string()
    .min(2, 'Key must be at least 2 chars')
    .max(64)
    .regex(/^[a-z0-9-]+$/, 'Key must be lowercase letters, numbers, or dashes'),
  name: z.string().min(2, 'Name is required').max(128),
  description: z.string().max(256).optional(),
});

type ProjectFormData = z.infer<typeof projectSchema>;

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const CreateProjectModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const { currentOrg, refetchUserAndOrgs } = useApp();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues: { key: '', name: '', description: '' },
  });

  const mutation = useMutation({
    mutationFn: (data: ProjectFormData) => {
      if (!currentOrg) throw new Error('No active organization');
      return projectApi.createProject(currentOrg.id, data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['projects'] });
      await refetchUserAndOrgs();
      reset();
      onClose();
    },
  });

  const onSubmit = (data: ProjectFormData) => {
    mutation.mutate(data);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create New Project"
      description="Projects organize feature flags and configuration across environments."
    >
      {mutation.isError && (
        <div role="alert" className="mb-4 p-3 rounded-md bg-status-danger/10 text-xs text-status-danger">
          {(mutation.error as { message?: string })?.message || 'Failed to create project'}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Project Name"
          placeholder="E.g. E-Commerce Platform"
          error={errors.name?.message}
          {...register('name')}
          required
        />

        <Input
          label="Project Key"
          placeholder="e.g. ecommerce-platform"
          helperText="Unique identifier used in code and APIs"
          error={errors.key?.message}
          {...register('key')}
          required
        />

        <Input
          label="Description (Optional)"
          placeholder="Brief summary of project scope"
          error={errors.description?.message}
          {...register('description')}
        />

        <div className="flex justify-end gap-2 pt-3 border-t border-border-subtle">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" isLoading={mutation.isPending}>
            Create Project
          </Button>
        </div>
      </form>
    </Modal>
  );
};
