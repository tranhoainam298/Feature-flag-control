import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { authApi } from './api';
import { useApp } from '../../context/AppContext';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { LogIn, Shield } from 'lucide-react';

const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormData = z.infer<typeof loginSchema>;

export const LoginForm: React.FC = () => {
  const { refetchUserAndOrgs } = useApp();
  const [serverError, setServerError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    try {
      setIsLoading(true);
      setServerError(null);
      await authApi.login(data.email, data.password);
      await refetchUserAndOrgs();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || 'Authentication failed. Verify credentials and try again.';
      setServerError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-sm">
      {/* Brand Mark */}
      <div className="flex flex-col items-center text-center mb-8">
        <div className="w-9 h-9 rounded-md bg-brand/10 border border-brand/20 flex items-center justify-center mb-4">
          <Shield className="w-4.5 h-4.5 text-brand" />
        </div>
        <h1 className="text-lg font-semibold text-primary tracking-tight">
          FlagOps Management Console
        </h1>
        <p className="text-xs text-muted mt-1">
          Feature Flag & Configuration Control Plane
        </p>
      </div>

      {/* Error Alert */}
      {serverError && (
        <div
          role="alert"
          className="mb-5 px-3 py-2.5 rounded-sm bg-status-danger-bg border border-status-danger-border text-xs text-status-danger font-medium"
        >
          {serverError}
        </div>
      )}

      {/* Login Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input
          label="Work Email"
          type="email"
          autoComplete="email"
          placeholder="you@company.com"
          error={errors.email?.message}
          {...register('email')}
          required
        />

        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          placeholder="••••••••"
          error={errors.password?.message}
          {...register('password')}
          required
        />

        <div className="pt-1">
          <Button
            type="submit"
            variant="primary"
            className="w-full h-9"
            isLoading={isLoading}
            leftIcon={<LogIn className="w-3.5 h-3.5" />}
          >
            Sign In to Organization
          </Button>
        </div>
      </form>

      {/* Security Footer */}
      <div className="mt-8 pt-5 border-t border-border-subtle text-center">
        <p className="text-[10px] text-muted font-mono uppercase tracking-wider">
          Multi-Tenant · TLS End-to-End Encrypted
        </p>
      </div>
    </div>
  );
};
