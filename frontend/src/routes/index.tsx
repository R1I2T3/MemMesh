import { createRoute, redirect, useNavigate } from '@tanstack/react-router';
import { Route as rootRoute } from './__root';
import { useEffect, useState, type FormEvent } from 'react';
import { apiFetch } from '../lib/api';
import { formatHealthStatus } from '../utils/health';
import { getStoredAuth } from '../utils/auth';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    const auth = getStoredAuth();
    if (auth) {
      throw redirect({ to: '/dashboard' });
    }
  },
  component: LoginHome,
});

function LoginHome() {
  const navigate = useNavigate();
  const [status, setStatus] = useState('Checking...');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiFetch('/api/health')
      .then(res => res.json())
      .then(data => {
        const health = formatHealthStatus(data.services || {});
        setStatus(health.overall);
      })
      .catch(() => setStatus('unreachable'));
  }, []);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('token', data.token);
        localStorage.setItem('role', data.role);
        navigate({ to: '/dashboard' });
      } else {
        setError('Invalid email or password');
      }
    } catch {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md flex flex-col gap-4">
        <div className="flex flex-col gap-1 text-center">
          <h1 className="text-3xl font-bold tracking-tight">MemMesh</h1>
          <p id="system-status" className="text-sm text-slate-400">System: {status}</p>
        </div>
        <Card className="bg-slate-900 border-slate-800 text-white">
          <form onSubmit={handleLogin}>
            <CardHeader>
              <CardTitle className="text-xl">Welcome Back</CardTitle>
              <CardDescription className="text-slate-400">Login to your account to continue</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <label htmlFor="email-input" className="text-sm font-medium">Email address</label>
                <Input
                  id="email-input"
                  type="email"
                  placeholder="name@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  className="bg-slate-950 border-slate-800 text-white placeholder:text-slate-500 focus-visible:ring-indigo-500 focus-visible:border-indigo-500"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label htmlFor="password-input" className="text-sm font-medium">Password</label>
                <Input
                  id="password-input"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="bg-slate-950 border-slate-800 text-white placeholder:text-slate-500 focus-visible:ring-indigo-500 focus-visible:border-indigo-500"
                />
              </div>
              {error && <p id="login-error" className="text-sm text-red-400 font-medium">{error}</p>}
            </CardContent>
            <CardFooter className="flex flex-col gap-2">
              <Button
                id="login-button"
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium"
              >
                {loading ? 'Logging in...' : 'Sign In'}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
