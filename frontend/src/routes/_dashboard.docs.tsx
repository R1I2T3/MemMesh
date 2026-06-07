import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/docs',
  component: () => <h2 id="docs-title">Document Ingestion Console</h2>,
});
