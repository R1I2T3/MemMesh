import { createRoute, redirect, useNavigate } from '@tanstack/react-router';
import { Route as rootRoute } from './__root';
import { useEffect, useState, type FormEvent } from 'react';
import { apiFetch } from '../lib/api';
import { formatHealthStatus } from '../utils/health';
import { getStoredAuth } from '../utils/auth';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { LayoutDashboardIcon } from 'lucide-react';

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
    <div className="min-h-screen bg-mesh-gradient flex items-center justify-center p-4">
      <div className="w-full max-w-sm flex flex-col gap-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 p-3 text-white shadow-sm">
            <LayoutDashboardIcon className="size-7" />
          </div>
          <div className="flex flex-col gap-0.5">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">MemMesh</h1>
            <p id="system-status" className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
              <span className={`size-1.5 rounded-full ${status === 'operational' ? 'bg-emerald-500' : status === 'unreachable' ? 'bg-destructive' : 'bg-amber-500'}`} />
              System: {status}
            </p>
          </div>
        </div>
        <Card className="bg-card border-border text-card-foreground shadow-sm">
          <form onSubmit={handleLogin}>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold tracking-tight">Welcome Back</CardTitle>
              <CardDescription className="text-xs text-muted-foreground">
                Sign in to your account to continue
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="email-input" className="text-xs font-medium text-foreground/80">
                  Email address
                </label>
                <Input
                  id="email-input"
                  type="email"
                  autoComplete="email"
                  placeholder="name@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  className="bg-background border-input text-foreground placeholder:text-muted-foreground/60 focus-visible:ring-2 focus-visible:ring-primary/20 h-9"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="password-input" className="text-xs font-medium text-foreground/80">
                  Password
                </label>
                <Input
                  id="password-input"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="bg-background border-input text-foreground placeholder:text-muted-foreground/60 focus-visible:ring-2 focus-visible:ring-primary/20 h-9"
                />
              </div>
              {error && (
                <p id="login-error" className="text-xs text-destructive font-medium flex items-center gap-1.5">
                  <span className="size-1.5 rounded-full bg-destructive shrink-0" />
                  {error}
                </p>
              )}
            </CardContent>
            <CardFooter className="pt-1">
              <Button
                id="login-button"
                type="submit"
                disabled={loading}
                className="w-full h-9 font-medium transition-all duration-200 active:scale-[0.98]"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="size-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    Logging in...
                  </span>
                ) : (
                  'Sign In'
                )}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
