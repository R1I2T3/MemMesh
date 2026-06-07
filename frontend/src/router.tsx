import { createRouter } from '@tanstack/react-router';
import { Route as rootRoute } from './routes/__root';
import { Route as indexRoute } from './routes/index';
import { Route as dashboardLayoutRoute } from './routes/_dashboard';

const routeTree = rootRoute.addChildren([indexRoute, dashboardLayoutRoute]);

export const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
