import React from 'react';
import { ConfigDiffResponse } from '../../types';
import { X, PlusCircle, AlertCircle, MinusCircle } from 'lucide-react';

interface ConfigDiffModalProps {
  title?: string;
  diff: ConfigDiffResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onPublishClick?: () => void;
}

export const ConfigDiffModal: React.FC<ConfigDiffModalProps> = ({
  title = 'Configuration Diff',
  diff,
  isOpen,
  onClose,
  onPublishClick,
}) => {
  if (!isOpen || !diff) return null;

  const addedEntries = Object.entries(diff.added || {});
  const changedEntries = Object.entries(diff.changed || {});
  const removedEntries = Object.entries(diff.removed || {});
  const totalChanges = addedEntries.length + changedEntries.length + removedEntries.length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-5xl rounded-md border border-border-default bg-surface p-5 shadow-2xl space-y-3.5 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-subtle pb-3">
          <div>
            <h3 className="text-sm font-semibold text-primary">{title}</h3>
            <p className="text-[11px] text-muted mt-0.5">
              {totalChanges} {totalChanges === 1 ? 'change' : 'changes'} compared to base configuration
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xs p-1 text-muted hover:bg-surface-elevated hover:text-primary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 3-column Diff View */}
        <div className="flex-1 overflow-y-auto">
          {totalChanges === 0 ? (
            <div className="p-10 text-center text-xs text-muted">
              No differences detected between these configuration versions.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Column 1: ADDED (Green) */}
              <div className="rounded-xs border border-status-success/30 bg-status-success/5 p-2.5 flex flex-col">
                <div className="flex items-center justify-between border-b border-status-success/20 pb-2 mb-2 text-status-success font-medium text-xs">
                  <span className="flex items-center gap-1.5">
                    <PlusCircle className="w-3.5 h-3.5" />
                    Added
                  </span>
                  <span className="rounded-xs bg-status-success/20 px-1.5 py-0.2 text-[10px] font-mono">
                    {addedEntries.length}
                  </span>
                </div>

                <div className="space-y-1.5 overflow-y-auto max-h-96 pr-1">
                  {addedEntries.length === 0 ? (
                    <span className="text-xs text-muted italic">None</span>
                  ) : (
                    addedEntries.map(([key, val]) => (
                      <div
                        key={key}
                        className="rounded-xs bg-surface p-2 border border-status-success/20 text-xs"
                      >
                        <div className="font-mono font-semibold text-status-success break-all">
                          +{key}
                        </div>
                        <div className="mt-1 font-mono text-[11px] text-secondary break-all bg-surface-elevated p-1 rounded-xs">
                          {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Column 2: CHANGED (Yellow/Amber) */}
              <div className="rounded-xs border border-status-warning/30 bg-status-warning/5 p-2.5 flex flex-col">
                <div className="flex items-center justify-between border-b border-status-warning/20 pb-2 mb-2 text-status-warning font-medium text-xs">
                  <span className="flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Changed
                  </span>
                  <span className="rounded-xs bg-status-warning/20 px-1.5 py-0.2 text-[10px] font-mono">
                    {changedEntries.length}
                  </span>
                </div>

                <div className="space-y-1.5 overflow-y-auto max-h-96 pr-1">
                  {changedEntries.length === 0 ? (
                    <span className="text-xs text-muted italic">None</span>
                  ) : (
                    changedEntries.map(([key, item]: [string, any]) => (
                      <div
                        key={key}
                        className="rounded-xs bg-surface p-2 border border-status-warning/20 text-xs"
                      >
                        <div className="font-mono font-semibold text-status-warning break-all">
                          ~ {key}
                        </div>
                        <div className="mt-1 space-y-1 font-mono text-[11px]">
                          <div className="rounded-xs bg-status-danger/10 p-1 text-status-danger border border-status-danger/20 break-all">
                            - {typeof item?.old === 'object' ? JSON.stringify(item.old) : String(item?.old)}
                          </div>
                          <div className="rounded-xs bg-status-success/10 p-1 text-status-success border border-status-success/20 break-all">
                            + {typeof item?.new === 'object' ? JSON.stringify(item.new) : String(item?.new)}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Column 3: REMOVED (Red) */}
              <div className="rounded-xs border border-status-danger/30 bg-status-danger/5 p-2.5 flex flex-col">
                <div className="flex items-center justify-between border-b border-status-danger/20 pb-2 mb-2 text-status-danger font-medium text-xs">
                  <span className="flex items-center gap-1.5">
                    <MinusCircle className="w-3.5 h-3.5" />
                    Removed
                  </span>
                  <span className="rounded-xs bg-status-danger/20 px-1.5 py-0.2 text-[10px] font-mono">
                    {removedEntries.length}
                  </span>
                </div>

                <div className="space-y-1.5 overflow-y-auto max-h-96 pr-1">
                  {removedEntries.length === 0 ? (
                    <span className="text-xs text-muted italic">None</span>
                  ) : (
                    removedEntries.map(([key, val]) => (
                      <div
                        key={key}
                        className="rounded-xs bg-surface p-2 border border-status-danger/20 text-xs"
                      >
                        <div className="font-mono font-semibold text-status-danger break-all">
                          -{key}
                        </div>
                        <div className="mt-1 font-mono text-[11px] text-muted line-through break-all bg-surface-elevated p-1 rounded-xs opacity-75">
                          {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xs border border-border-default bg-surface px-3 py-1.5 text-xs font-medium text-secondary hover:bg-surface-elevated hover:text-primary transition-colors"
          >
            Close
          </button>
          {onPublishClick && totalChanges > 0 && (
            <button
              type="button"
              onClick={() => {
                onClose();
                onPublishClick();
              }}
              className="rounded-xs bg-brand px-3.5 py-1.5 text-xs font-medium text-white hover:bg-brand-hover shadow-xs transition-colors"
            >
              Proceed to Publish
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
