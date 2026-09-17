import React from 'react';

interface Props {
  icon: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<Props> = ({ icon, title, description, action }) => {
  return (
    <div className="border border-border-subtle border-dashed rounded-md px-8 py-12 flex flex-col items-center justify-center text-center">
      <div className="text-muted mb-3">{icon}</div>
      <h3 className="text-xs font-semibold text-primary mb-1">{title}</h3>
      {description && (
        <p className="text-[11px] text-muted max-w-xs mb-4">{description}</p>
      )}
      {action}
    </div>
  );
};
