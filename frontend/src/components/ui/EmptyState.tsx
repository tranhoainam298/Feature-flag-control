import React from 'react';

export interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-border-default rounded-lg bg-surface/50 my-6">
      <div className="p-3 bg-surface-elevated rounded-full text-secondary mb-3.5 border border-border-subtle">
        {icon}
      </div>
      <h3 className="text-base font-medium text-primary mb-1">{title}</h3>
      <p className="text-sm text-secondary max-w-sm mb-5">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
};
