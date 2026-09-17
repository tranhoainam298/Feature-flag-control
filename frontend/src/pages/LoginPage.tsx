import React from 'react';
import { Navigate } from 'react-router-dom';
import { LoginForm } from '../features/auth/LoginForm';
import { useApp } from '../context/AppContext';

export const LoginPage: React.FC = () => {
  const { isAuthenticated } = useApp();

  if (isAuthenticated) {
    return <Navigate to="/flags" replace />;
  }

  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
      <LoginForm />
    </div>
  );
};
