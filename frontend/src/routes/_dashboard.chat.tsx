import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/chat',
  component: () => <h2 id="chat-title">Chat Interface Console</h2>,
});
