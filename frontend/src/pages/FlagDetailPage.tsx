import React, { useState } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { flagApi } from '../features/flags/api';
import { FlagHeader } from '../features/flags/FlagHeader';
import { FlagVariations } from '../features/flags/FlagVariations';
import { FlagSimulator } from '../features/flags/FlagSimulator';
import { RuleBuilder } from '../features/targeting/RuleBuilder';
import { useApp } from '../context/AppContext';
import { ArrowLeft, Layers, Crosshair, Terminal, Settings } from 'lucide-react';
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

  if (isLoading) return <SkeletonTable rows={6} columns={3} />;
  if (isError || !flag) {
    return <ErrorAlert error={error || 'Flag not found'} onRetry={() => refetch()} />;
  }

  const tabs = [
    { key: 'targeting', label: 'Targeting Rules', icon: Crosshair },
    { key: 'simulator', label: 'Evaluation Workbench', icon: Terminal },
    { key: 'variations', label: `Variations (${flag.variations.length})`, icon: Settings },
  ];

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <Link
        to="/flags"
        className="inline-flex items-center gap-1 text-[11px] text-muted hover:text-primary transition-colors font-medium"
      >
        <ArrowLeft className="w-3 h-3" />
        <span>Flags</span>
      </Link>

      {/* Header */}
      <FlagHeader flag={flag} />

      {/* Environment Bar */}
      <div className="border border-border-subtle rounded-md bg-surface overflow-hidden">
        <div className="px-4 py-2.5 border-b border-border-subtle bg-surface-elevated flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-muted" />
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider">
              Environment
            </span>
          </div>

          {/* Env Tabs */}
          <div className="flex items-center gap-0.5 bg-surface-active/40 p-0.5 rounded-sm border border-border-subtle">
            {environments.map((env) => (
              <button
                key={env.id}
                type="button"
                onClick={() => setSelectedEnvId(env.id)}
                className={`px-2.5 py-1 text-[11px] font-medium rounded-xs transition-all cursor-pointer ${
                  activeEnvId === env.id
                    ? 'bg-surface-elevated text-primary shadow-sm border border-border-default'
                    : 'text-muted hover:text-secondary'
                }`}
              >
                {env.name}
              </button>
            ))}
          </div>
        </div>

        {/* Toggle Status */}
        <div className="px-4 py-2.5 flex items-center justify-between">
          <div>
            <span className="text-xs font-medium text-primary">
              Flag state in {activeEnv?.name || 'environment'}
            </span>
          </div>
          <div className="flex items-center gap-2.5">
            <span
              className={`text-[10px] font-mono font-semibold ${
                setting?.enabled ? 'text-brand' : 'text-muted'
              }`}
            >
              {setting?.enabled ? 'ENABLED' : 'DISABLED'}
            </span>
            <Switch
              checked={setting?.enabled ?? false}
              onChange={(checked) => toggleMutation.mutate(checked)}
              isLoading={isSettingLoading || toggleMutation.isPending}
              ariaLabel={`Toggle ${flag.key} in ${activeEnv?.name}`}
              size="sm"
            />
          </div>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="border-b border-border-subtle">
        <nav className="flex gap-0" aria-label="Flag detail tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setSearchParams({ tab: tab.key })}
                className={`flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium border-b-2 transition-colors ${
                  isActive
                    ? 'border-brand text-brand'
                    : 'border-transparent text-muted hover:text-secondary'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Panels */}
      {activeTab === 'targeting' && (
        <div className="space-y-3">
          <div>
            <h3 className="text-xs font-semibold text-primary">
              Targeting Rules — {activeEnv?.name}
            </h3>
            <p className="text-[10px] text-muted mt-0.5">
              Rules evaluated top-to-bottom by priority. First match wins.
            </p>
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
          envName={activeEnv?.name || 'Environment'}
        />
      )}

      {activeTab === 'variations' && (
        <FlagVariations variations={flag.variations} />
      )}
    </div>
  );
};
