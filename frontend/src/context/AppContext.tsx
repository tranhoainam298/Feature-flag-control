import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, Organization, Project, Environment } from '../types';
import { clearAuthTokens, getAccessToken } from '../lib/api';
import { api } from '../lib/api';

interface AppContextType {
  user: User | null;
  currentOrg: Organization | null;
  currentProject: Project | null;
  currentEnvironment: Environment | null;
  projects: Project[];
  environments: Environment[];
  isLoading: boolean;
  isAuthenticated: boolean;
  setCurrentProject: (project: Project) => void;
  setCurrentEnvironment: (env: Environment) => void;
  refetchUserAndOrgs: () => Promise<void>;
  logout: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const SELECTED_PROJECT_KEY = 'flagops_selected_project_id';
const SELECTED_ENV_KEY = 'flagops_selected_env_id';

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [currentOrg, setCurrentOrg] = useState<Organization | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProjectState] = useState<Project | null>(null);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [currentEnvironment, setCurrentEnvironmentState] = useState<Environment | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!getAccessToken());

  const logout = useCallback(() => {
    clearAuthTokens();
    setUser(null);
    setCurrentOrg(null);
    setProjects([]);
    setCurrentProjectState(null);
    setEnvironments([]);
    setCurrentEnvironmentState(null);
    setIsAuthenticated(false);
  }, []);

  const fetchEnvironmentsForProject = useCallback(async (projectId: string) => {
    try {
      const res = await api.get<Environment[]>(`/api/v1/projects/${projectId}/environments`);
      const envList = res.data;
      setEnvironments(envList);

      const savedEnvId = localStorage.getItem(SELECTED_ENV_KEY);
      const matched = envList.find((e) => e.id === savedEnvId) || envList[0] || null;
      setCurrentEnvironmentState(matched);
      if (matched) {
        localStorage.setItem(SELECTED_ENV_KEY, matched.id);
      }
    } catch {
      setEnvironments([]);
      setCurrentEnvironmentState(null);
    }
  }, []);

  const setCurrentProject = useCallback(
    (project: Project) => {
      setCurrentProjectState(project);
      localStorage.setItem(SELECTED_PROJECT_KEY, project.id);
      fetchEnvironmentsForProject(project.id);
    },
    [fetchEnvironmentsForProject]
  );

  const setCurrentEnvironment = useCallback((env: Environment) => {
    setCurrentEnvironmentState(env);
    localStorage.setItem(SELECTED_ENV_KEY, env.id);
  }, []);

  const refetchUserAndOrgs = useCallback(async () => {
    if (!getAccessToken()) {
      setIsLoading(false);
      setIsAuthenticated(false);
      return;
    }

    try {
      setIsLoading(true);
      const userRes = await api.get<User>('/api/v1/auth/me');
      setUser(userRes.data);
      setIsAuthenticated(true);

      const orgsRes = await api.get<Organization[]>('/api/v1/organizations');
      const orgList = orgsRes.data;
      if (orgList.length > 0) {
        const org = orgList[0];
        setCurrentOrg(org);

        const projectsRes = await api.get<Project[]>(`/api/v1/organizations/${org.id}/projects`);
        const projList = projectsRes.data;
        setProjects(projList);

        const savedProjId = localStorage.getItem(SELECTED_PROJECT_KEY);
        const selectedProj = projList.find((p) => p.id === savedProjId) || projList[0] || null;
        setCurrentProjectState(selectedProj);

        if (selectedProj) {
          localStorage.setItem(SELECTED_PROJECT_KEY, selectedProj.id);
          await fetchEnvironmentsForProject(selectedProj.id);
        }
      }
    } catch {
      logout();
    } finally {
      setIsLoading(false);
    }
  }, [fetchEnvironmentsForProject, logout]);

  useEffect(() => {
    refetchUserAndOrgs();

    const handleLogoutEvent = () => logout();
    window.addEventListener('flagops-auth-logout', handleLogoutEvent);
    return () => window.removeEventListener('flagops-auth-logout', handleLogoutEvent);
  }, [refetchUserAndOrgs, logout]);

  return (
    <AppContext.Provider
      value={{
        user,
        currentOrg,
        currentProject,
        currentEnvironment,
        projects,
        environments,
        isLoading,
        isAuthenticated,
        setCurrentProject,
        setCurrentEnvironment,
        refetchUserAndOrgs,
        logout,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = (): AppContextType => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
