import { createRoute, redirect } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/dashboard/chat' });
  },
});
