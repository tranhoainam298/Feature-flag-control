import React, { useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { flagApi } from '../features/flags/api';
import { FlagHeader } from '../features/flags/FlagHeader';
import { FlagVariations } from '../features/flags/FlagVariations';
import { FlagSimulator } from '../features/flags/FlagSimulator';
import { RuleBuilder } from '../features/targeting/RuleBuilder';
import { useApp } from '../context/AppContext';
import { ArrowLeft, Layers, Sliders, Play, Settings } from 'lucide-react';
import { Switch } from '../components/ui/Switch';
import { SkeletonTable } from '../components/ui/SkeletonTable';
import { ErrorAlert } from '../components/ui/ErrorAlert';

export const FlagDetailPage: React.FC = () => {
  const { id: flagId } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { environments, currentEnvironment } = useApp();
  const queryClient = useQueryClient();

  const activeTab = searchParams.get('tab') || 'targeting';

  const [selectedEnvId, setSelectedEnvId] = useState<string>(
    currentEnvironment?.id || environments[0]?.id || ''
  );

  const activeEnvId = selectedEnvId || currentEnvironment?.id || environments[0]?.id || '';
  const activeEnv = environments.find((e) => e.id === activeEnvId) || currentEnvironment;

  const {
    data: flag,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['flag', flagId],
    queryFn: () => flagApi.getFlag(flagId!),
    enabled: !!flagId,
  });

  const settingQueryKey = ['flag-setting', flagId, activeEnvId];
  const { data: setting, isLoading: isSettingLoading } = useQuery({
    queryKey: settingQueryKey,
    queryFn: () => flagApi.getFlagSetting(flagId!, activeEnvId),
    enabled: !!flagId && !!activeEnvId,
  });

  const toggleMutation = useMutation({
    mutationFn: (newEnabled: boolean) =>
      flagApi.updateFlagSetting(flagId!, activeEnvId, { enabled: newEnabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingQueryKey });
      queryClient.invalidateQueries({ queryKey: ['flags'] });
    },
  });

  if (isLoading) return <SkeletonTable rows={4} columns={3} />;
  if (isError || !flag) {
    return <ErrorAlert error={error || 'Flag not found'} onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      {/* Back Link */}
      <div>
        <Link
          to="/flags"
          className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-primary transition-colors font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Quay lại danh sách Flag</span>
        </Link>
      </div>

      {/* Header */}
      <FlagHeader flag={flag} />

      {/* Environment Selector & Switch */}
      <div className="border border-border-default rounded-xl bg-surface overflow-hidden shadow-xs">
        <div className="p-3.5 border-b border-border-subtle bg-surface-elevated flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-brand" />
            <span className="text-xs font-semibold text-primary uppercase tracking-wide">
              Môi trường làm việc:
            </span>
          </div>

          {/* Environment Tabs */}
          <div className="flex items-center gap-1 bg-surface-active/50 p-1 rounded-lg border border-border-subtle">
            {environments.map((env) => (
              <button
                key={env.id}
                type="button"
                onClick={() => setSelectedEnvId(env.id)}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-all cursor-pointer ${
                  activeEnvId === env.id
                    ? 'bg-surface-elevated text-primary shadow-xs border border-border-default font-semibold'
                    : 'text-muted hover:text-primary'
                }`}
              >
                {env.name}
              </button>
            ))}
          </div>
        </div>

        {/* Environment Toggle & Status */}
        <div className="p-4 flex items-center justify-between">
          <div>
            <h4 className="text-sm font-medium text-primary">
              Trạng thái Flag tại {activeEnv?.name || 'Môi trường'}
            </h4>
            <p className="text-xs text-muted mt-0.5">
              Khi TẮT, cờ sẽ trả về fallback variation mà không chạy bất kỳ quy tắc targeting nào.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`text-xs font-mono font-semibold ${
                setting?.enabled ? 'text-flag-on' : 'text-muted'
              }`}
            >
              {setting?.enabled ? 'BẬT (ENABLED)' : 'TẮT (DISABLED)'}
            </span>
            <Switch
              checked={setting?.enabled ?? false}
              onChange={(checked) => toggleMutation.mutate(checked)}
              isLoading={isSettingLoading || toggleMutation.isPending}
              ariaLabel={`Bật tắt flag ${flag.key} trong ${activeEnv?.name}`}
            />
          </div>
        </div>
      </div>

      {/* Main Tab Bar */}
      <div className="border-b border-border-default">
        <nav className="flex space-x-6" aria-label="Tabs">
          <button
            type="button"
            onClick={() => setSearchParams({ tab: 'targeting' })}
            className={`flex items-center gap-2 py-3 border-b-2 text-xs font-semibold transition-colors ${
              activeTab === 'targeting'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-muted hover:text-primary'
            }`}
          >
            <Sliders className="w-4 h-4" />
            <span>Targeting & Quy tắc</span>
          </button>

          <button
            type="button"
            onClick={() => setSearchParams({ tab: 'simulator' })}
            className={`flex items-center gap-2 py-3 border-b-2 text-xs font-semibold transition-colors ${
              activeTab === 'simulator'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-muted hover:text-primary'
            }`}
          >
            <Play className="w-4 h-4" />
            <span>Mô phỏng đánh giá (Simulator)</span>
          </button>

          <button
            type="button"
            onClick={() => setSearchParams({ tab: 'variations' })}
            className={`flex items-center gap-2 py-3 border-b-2 text-xs font-semibold transition-colors ${
              activeTab === 'variations'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-muted hover:text-primary'
            }`}
          >
            <Settings className="w-4 h-4" />
            <span>Variations ({flag.variations.length})</span>
          </button>
        </nav>
      </div>

      {/* Tab Panels */}
      {activeTab === 'targeting' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-primary">
                Quy tắc Targeting — {activeEnv?.name}
              </h3>
              <p className="text-xs text-muted">
                Quy tắc được đánh giá từ trên xuống dưới (độ ưu tiên #1 trước). Khi khớp điều kiện, rollout sẽ phân phối theo tỉ lệ.
              </p>
            </div>
          </div>

          <RuleBuilder
            flagId={flag.id}
            envId={activeEnvId}
            variations={flag.variations}
          />
        </div>
      )}

      {activeTab === 'simulator' && (
        <FlagSimulator
          flagId={flag.id}
          envId={activeEnvId}
          envName={activeEnv?.name || 'Môi trường'}
        />
      )}

      {activeTab === 'variations' && (
        <FlagVariations variations={flag.variations} />
      )}
    </div>
  );
};
