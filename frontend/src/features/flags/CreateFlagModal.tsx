import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { flagApi } from './api';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Button } from '../../components/ui/Button';
import { FlagType } from '../../types';

const flagSchema = z.object({
  key: z
    .string()
    .min(1, 'Key is required')
    .max(160)
    .regex(/^[a-zA-Z0-9._-]+$/, 'Only letters, numbers, dots, dashes, and underscores allowed'),
  name: z.string().min(1, 'Name is required').max(200),
  description: z.string().max(500).optional(),
  type: z.enum(['BOOLEAN', 'STRING', 'NUMBER', 'JSON']),
  tagsInput: z.string().optional(),
});

type FlagFormData = z.infer<typeof flagSchema>;

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
}

export const CreateFlagModal: React.FC<Props> = ({ isOpen, onClose, projectId }) => {
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FlagFormData>({
    resolver: zodResolver(flagSchema),
    defaultValues: {
      key: '',
      name: '',
      description: '',
      type: 'BOOLEAN',
      tagsInput: '',
    },
  });

  const mutation = useMutation({
    mutationFn: (data: FlagFormData) => {
      const tags = data.tagsInput
        ? data.tagsInput
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean)
        : [];

      return flagApi.createFlag(projectId, {
        key: data.key,
        name: data.name,
        description: data.description || null,
        type: data.type as FlagType,
        tags,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flags', projectId] });
      reset();
      onClose();
    },
  });

  const onSubmit = (data: FlagFormData) => {
    mutation.mutate(data);
  };

  const typeOptions = [
    { value: 'BOOLEAN', label: 'Boolean (True / False)' },
    { value: 'STRING', label: 'String (Multivariate text)' },
    { value: 'NUMBER', label: 'Number (Numeric values)' },
    { value: 'JSON', label: 'JSON (Dynamic schema/object)' },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create Feature Flag"
      description="Create a runtime feature toggle for your project."
    >
      {mutation.isError && (
        <div role="alert" className="mb-4 p-3 rounded-md bg-status-danger/10 text-xs text-status-danger">
          {(mutation.error as { message?: string })?.message || 'Failed to create flag'}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Flag Key"
          placeholder="e.g. checkout-v2"
          helperText="Unique identifier used in code via client.is_enabled('key')"
          error={errors.key?.message}
          {...register('key')}
          required
        />

        <Input
          label="Flag Name"
          placeholder="e.g. New Checkout Flow"
          error={errors.name?.message}
          {...register('name')}
          required
        />

        <Select
          label="Flag Type"
          options={typeOptions}
          error={errors.type?.message}
          {...register('type')}
        />

        <Input
          label="Tags (Comma separated)"
          placeholder="e.g. checkout, payment, mobile"
          helperText="Used to group and filter flags"
          error={errors.tagsInput?.message}
          {...register('tagsInput')}
        />

        <Input
          label="Description (Optional)"
          placeholder="Explain what this flag controls and why"
          error={errors.description?.message}
          {...register('description')}
        />

        <div className="flex justify-end gap-2 pt-3 border-t border-border-subtle">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" isLoading={mutation.isPending}>
            Create Flag
          </Button>
        </div>
      </form>
    </Modal>
  );
};
