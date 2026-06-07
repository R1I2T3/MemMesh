import { createRoute, Outlet } from '@tanstack/react-router';
import { Route as rootRoute } from './__root';

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
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
