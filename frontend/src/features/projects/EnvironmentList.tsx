import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectApi } from './api';
import { Environment } from '../../types';
import { Layers, Plus, CheckCircle2 } from 'lucide-react';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import { SkeletonTable } from '../../components/ui/SkeletonTable';
import { ErrorAlert } from '../../components/ui/ErrorAlert';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const envSchema = z.object({
  key: z
    .string()
    .min(2)
    .max(32)
    .regex(/^[a-z0-9-]+$/, 'Key must be lowercase letters, numbers, or dashes'),
  name: z.string().min(2).max(64),
  description: z.string().optional(),
  is_production: z.boolean(),
});

type EnvFormData = z.infer<typeof envSchema>;

export const EnvironmentList: React.FC<{ projectId: string }> = ({ projectId }) => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const {
    data: environments,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['environments', projectId],
    queryFn: () => projectApi.listEnvironments(projectId),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EnvFormData>({
    resolver: zodResolver(envSchema),
    defaultValues: { key: '', name: '', description: '', is_production: false },
  });

  const createMutation = useMutation({
    mutationFn: (data: EnvFormData) => projectApi.createEnvironment(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environments', projectId] });
      reset();
      setIsModalOpen(false);
    },
  });

  if (isLoading) return <SkeletonTable rows={3} columns={4} />;
  if (isError) return <ErrorAlert error={error} onRetry={() => refetch()} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-primary">Target Environments</h3>
          <p className="text-xs text-muted">
            Configure feature flags and rollout targets for each environment.
          </p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => setIsModalOpen(true)}
          leftIcon={<Plus className="w-3.5 h-3.5" />}
        >
          Add Environment
        </Button>
      </div>

      <div className="border border-border-default rounded-lg overflow-hidden bg-surface">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-elevated border-b border-border-subtle text-muted uppercase font-mono text-[10px]">
            <tr>
              <th className="p-3">Environment Name</th>
              <th className="p-3">Key</th>
              <th className="p-3">Production</th>
              <th className="p-3">Ruleset Version</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle text-secondary">
            {environments?.map((env: Environment) => (
              <tr key={env.id} className="hover:bg-surface-hover/50 transition-colors">
                <td className="p-3 font-medium text-primary flex items-center gap-2">
                  <Layers className="w-4 h-4 text-brand" />
                  <span>{env.name}</span>
                </td>
                <td className="p-3 font-mono text-muted">{env.key}</td>
                <td className="p-3">
                  {env.is_production ? (
                    <Badge variant="warning" size="sm">
                      PROD
                    </Badge>
                  ) : (
                    <Badge variant="outline" size="sm">
                      NON-PROD
                    </Badge>
                  )}
                </td>
                <td className="p-3 font-mono text-primary flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-flag-on" />
                  <span>v{env.ruleset_version}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create Environment Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create Environment"
        description="Add a new deployment target to this project."
      >
        <form
          onSubmit={handleSubmit((data) => createMutation.mutate(data))}
          className="space-y-4"
        >
          <Input
            label="Environment Name"
            placeholder="e.g. Staging"
            error={errors.name?.message}
            {...register('name')}
            required
          />
          <Input
            label="Key"
            placeholder="e.g. staging"
            error={errors.key?.message}
            {...register('key')}
            required
          />
          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="is_prod_checkbox"
              className="rounded-xs border-border-default bg-surface-elevated text-brand focus:ring-brand"
              {...register('is_production')}
            />
            <label htmlFor="is_prod_checkbox" className="text-xs text-secondary font-medium">
              Is Production Environment (Protects against accidental rollout)
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-border-subtle">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={createMutation.isPending}>
              Create
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
