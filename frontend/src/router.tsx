import { createRouter } from '@tanstack/react-router';
import { Route as rootRoute } from './routes/__root';
import { Route as indexRoute } from './routes/index';
import { Route as dashboardLayoutRoute } from './routes/_dashboard';
import { Route as chatRoute } from './routes/_dashboard.chat';
import { Route as docsRoute } from './routes/_dashboard.docs';

const routeTree = rootRoute.addChildren([
  indexRoute,
  dashboardLayoutRoute.addChildren([chatRoute, docsRoute]),
]);

export const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

