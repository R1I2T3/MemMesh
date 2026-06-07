import { createRoute, Outlet, useNavigate } from '@tanstack/react-router';
import { Route as rootRoute } from './__root';
import { useEffect } from 'react';
import { getStoredAuth } from '../utils/auth';

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
  component: DashboardLayout,
});

function DashboardLayout() {
  const navigate = useNavigate();
  const auth = getStoredAuth();

  useEffect(() => {
    if (!auth) {
      navigate({ to: '/' });
    }
  }, [auth, navigate]);

  if (!auth) return null;

  return (
    <div style={{ padding: '2rem' }}>
      <h1 id="dashboard-header">Dashboard</h1>
      <Outlet />
    </div>
  );
}

