import { createRoute, Outlet, redirect } from '@tanstack/react-router';
import { Route as rootRoute } from './__root';
import { getStoredAuth } from '../utils/auth';

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
  beforeLoad: () => {
    const auth = getStoredAuth();
    if (!auth) {
      throw redirect({ to: '/' });
    }
  },
  component: DashboardLayout,
});

function DashboardLayout() {
  return (
    <div style={{ padding: '2rem' }}>
      <h1 id="dashboard-header">Dashboard</h1>
      <Outlet />
    </div>
  );
}
