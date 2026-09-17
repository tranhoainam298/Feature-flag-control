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
  title = 'So sánh thay đổi cấu hình (Diff)',
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
      <div className="w-full max-w-5xl rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <div>
            <h3 className="text-base font-semibold text-[var(--text-primary)]">{title}</h3>
            <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
              Tổng cộng {totalChanges} thay đổi so với phiên bản so sánh
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 3-column Diff View */}
        <div className="flex-1 overflow-y-auto">
          {totalChanges === 0 ? (
            <div className="p-12 text-center text-sm text-[var(--text-tertiary)]">
              Không có bất kỳ thay đổi nào giữa hai phiên bản cấu hình này.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Column 1: ADDED (Green) */}
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 flex flex-col">
                <div className="flex items-center justify-between border-b border-emerald-500/20 pb-2 mb-2 text-emerald-400 font-semibold text-xs">
                  <span className="flex items-center gap-1.5">
                    <PlusCircle className="w-3.5 h-3.5" />
                    Được thêm mới (Added)
                  </span>
                  <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px]">
                    {addedEntries.length}
                  </span>
                </div>

                <div className="space-y-2 overflow-y-auto max-h-96 pr-1">
                  {addedEntries.length === 0 ? (
                    <span className="text-xs text-[var(--text-tertiary)] italic">Không có</span>
                  ) : (
                    addedEntries.map(([key, val]) => (
                      <div
                        key={key}
                        className="rounded bg-[var(--surface)] p-2 border border-emerald-500/20 text-xs"
                      >
                        <div className="font-mono font-semibold text-emerald-300 break-all">
                          +{key}
                        </div>
                        <div className="mt-1 font-mono text-[11px] text-[var(--text-secondary)] break-all bg-[var(--surface-sunken)] p-1 rounded">
                          {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Column 2: CHANGED (Yellow/Amber) */}
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 flex flex-col">
                <div className="flex items-center justify-between border-b border-amber-500/20 pb-2 mb-2 text-amber-400 font-semibold text-xs">
                  <span className="flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Đã thay đổi (Changed)
                  </span>
                  <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px]">
                    {changedEntries.length}
                  </span>
                </div>

                <div className="space-y-2 overflow-y-auto max-h-96 pr-1">
                  {changedEntries.length === 0 ? (
                    <span className="text-xs text-[var(--text-tertiary)] italic">Không có</span>
                  ) : (
                    changedEntries.map(([key, item]: [string, any]) => (
                      <div
                        key={key}
                        className="rounded bg-[var(--surface)] p-2 border border-amber-500/20 text-xs"
                      >
                        <div className="font-mono font-semibold text-amber-300 break-all">
                          ~ {key}
                        </div>
                        <div className="mt-1 space-y-1 font-mono text-[11px]">
                          <div className="rounded bg-rose-500/10 p-1 text-rose-300 border border-rose-500/20 break-all">
                            - {typeof item?.old === 'object' ? JSON.stringify(item.old) : String(item?.old)}
                          </div>
                          <div className="rounded bg-emerald-500/10 p-1 text-emerald-300 border border-emerald-500/20 break-all">
                            + {typeof item?.new === 'object' ? JSON.stringify(item.new) : String(item?.new)}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Column 3: REMOVED (Red) */}
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 flex flex-col">
                <div className="flex items-center justify-between border-b border-rose-500/20 pb-2 mb-2 text-rose-400 font-semibold text-xs">
                  <span className="flex items-center gap-1.5">
                    <MinusCircle className="w-3.5 h-3.5" />
                    Bị xóa bỏ (Removed)
                  </span>
                  <span className="rounded-full bg-rose-500/20 px-2 py-0.5 text-[10px]">
                    {removedEntries.length}
                  </span>
                </div>

                <div className="space-y-2 overflow-y-auto max-h-96 pr-1">
                  {removedEntries.length === 0 ? (
                    <span className="text-xs text-[var(--text-tertiary)] italic">Không có</span>
                  ) : (
                    removedEntries.map(([key, val]) => (
                      <div
                        key={key}
                        className="rounded bg-[var(--surface)] p-2 border border-rose-500/20 text-xs"
                      >
                        <div className="font-mono font-semibold text-rose-300 break-all">
                          -{key}
                        </div>
                        <div className="mt-1 font-mono text-[11px] text-[var(--text-secondary)] line-through break-all bg-[var(--surface-sunken)] p-1 rounded opacity-70">
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
        <div className="flex items-center justify-end gap-2 border-t border-[var(--border)] pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
          >
            Đóng
          </button>
          {onPublishClick && totalChanges > 0 && (
            <button
              type="button"
              onClick={() => {
                onClose();
                onPublishClick();
              }}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm"
            >
              Tiến hành phát hành
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
