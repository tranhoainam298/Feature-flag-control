import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { authApi } from './api';
import { useApp } from '../../context/AppContext';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { LogIn, Sparkles } from 'lucide-react';

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
    setValue,
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
      const msg = (err as { message?: string })?.message || 'Login failed. Please verify credentials.';
      setServerError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFillDemo = (email: string, pass: string) => {
    setValue('email', email, { shouldValidate: true });
    setValue('password', pass, { shouldValidate: true });
    setServerError(null);
  };

  return (
    <div className="w-full max-w-md p-8 bg-surface border border-border-default rounded-xl shadow-2xl">
      <div className="flex flex-col items-center text-center mb-8">
        <div className="w-10 h-10 rounded-lg bg-brand flex items-center justify-center text-white mb-3 shadow-md shadow-brand/30">
          <Sparkles className="w-5 h-5" />
        </div>
        <h1 className="text-2xl font-bold text-primary tracking-tight">Sign in to FlagOps</h1>
        <p className="text-xs text-secondary mt-1">Feature Flag & Config Management Platform</p>
      </div>

      {serverError && (
        <div
          role="alert"
          className="mb-6 p-3 rounded-md bg-status-danger/10 border border-status-danger/30 text-xs text-status-danger font-medium"
        >
          {serverError}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input
          label="Email Address"
          type="email"
          autoComplete="email"
          placeholder="engineer@demo.local"
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

        <div className="pt-2">
          <Button
            type="submit"
            variant="primary"
            className="w-full h-10"
            isLoading={isLoading}
            leftIcon={<LogIn className="w-4 h-4" />}
          >
            Sign In
          </Button>
        </div>
      </form>

      {/* Demo Credentials Helper */}
      <div className="mt-8 pt-6 border-t border-border-subtle">
        <p className="text-[11px] font-medium text-muted uppercase tracking-wider mb-2 text-center">
          Quick Demo Login
        </p>
        <div className="flex flex-col gap-1.5">
          <button
            type="button"
            onClick={() => handleFillDemo('owner@demo.local', 'demo1234')}
            className="text-xs text-left px-3 py-2 rounded-md bg-surface-elevated hover:bg-surface-hover border border-border-subtle text-secondary hover:text-primary transition-colors flex items-center justify-between"
          >
            <span className="font-mono text-primary">owner@demo.local</span>
            <span className="text-[10px] text-brand uppercase font-mono">Owner</span>
          </button>
          <button
            type="button"
            onClick={() => handleFillDemo('dev@demo.local', 'demo1234')}
            className="text-xs text-left px-3 py-2 rounded-md bg-surface-elevated hover:bg-surface-hover border border-border-subtle text-secondary hover:text-primary transition-colors flex items-center justify-between"
          >
            <span className="font-mono text-primary">dev@demo.local</span>
            <span className="text-[10px] text-amber-400 uppercase font-mono">Developer</span>
          </button>
        </div>
      </div>
    </div>
  );
};
