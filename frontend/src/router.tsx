import { createRouter } from '@tanstack/react-router';
import { Route as rootRoute } from './routes/__root';
import { Route as indexRoute } from './routes/index';
import { Route as dashboardLayoutRoute } from './routes/_dashboard';
import { Route as dashboardIndexRoute } from './routes/_dashboard.index';
import { Route as chatRoute } from './routes/_dashboard.chat';
import { Route as docsRoute } from './routes/_dashboard.docs';
import { Route as adminRoute } from './routes/_dashboard.admin';
import { Route as evalRoute } from './routes/_dashboard.eval';
import { Route as analyticsRoute } from './routes/_dashboard.analytics';
import { Route as graphRoute } from './routes/_dashboard.graph';

const routeTree = rootRoute.addChildren([
  indexRoute,
  dashboardLayoutRoute.addChildren([dashboardIndexRoute, chatRoute, docsRoute, adminRoute, evalRoute, analyticsRoute, graphRoute]),
]);

export const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

