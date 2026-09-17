import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/query-client';
import { AppProvider } from './context/AppContext';
import { ThemeProvider } from './context/ThemeContext';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { FlagsPage } from './pages/FlagsPage';
import { FlagDetailPage } from './pages/FlagDetailPage';
import { FlagHealthPage } from './pages/FlagHealthPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { SegmentsPage } from './pages/SegmentsPage';
import { ConfigPage } from './pages/ConfigPage';
import { ConfigDetailPage } from './pages/ConfigDetailPage';
import { AuditPage } from './pages/AuditPage';
import { ChangeRequestsPage } from './pages/ChangeRequestsPage';

export default function App(): React.ReactElement {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AppProvider>
          <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/flags" replace />} />
              <Route path="flags" element={<FlagsPage />} />
              <Route path="flags/:id" element={<FlagDetailPage />} />
              <Route path="change-requests" element={<ChangeRequestsPage />} />
              <Route path="health" element={<FlagHealthPage />} />
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="projects/:id" element={<ProjectDetailPage />} />
              <Route path="segments" element={<SegmentsPage />} />
              <Route path="config" element={<ConfigPage />} />
              <Route path="config/:namespaceId" element={<ConfigDetailPage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="*" element={<Navigate to="/flags" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AppProvider>
    </ThemeProvider>
  </QueryClientProvider>
  );
}
