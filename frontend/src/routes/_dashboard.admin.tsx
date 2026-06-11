import { createRoute, redirect } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { TeamsTab } from '@/components/admin/TeamsTab';
import { UsersTab } from '@/components/admin/UsersTab';
import { getStoredAuth } from '../utils/auth';
import { ShieldIcon } from 'lucide-react';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/admin',
  beforeLoad: () => {
    const auth = getStoredAuth();
    if (!auth || auth.role !== 'superadmin') {
      throw redirect({ to: '/dashboard/chat' });
    }
  },
  component: AdminPanelConsole,
});

function AdminPanelConsole() {
  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto w-full">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center rounded-xl bg-indigo-500/10 p-2.5 text-indigo-600 dark:text-indigo-400">
          <ShieldIcon className="size-5" />
        </div>
        <div className="flex flex-col gap-0.5">
          <h2 id="admin-title" className="text-xl font-bold tracking-tight">
            Admin Panel
          </h2>
          <p className="text-xs text-muted-foreground">Manage teams, users, and memberships</p>
        </div>
      </div>

      <Tabs defaultValue="teams" className="w-full">
        <TabsList className="mb-5">
          <TabsTrigger value="teams" id="tab-teams" className="text-xs">
            Teams Management
          </TabsTrigger>
          <TabsTrigger value="users" id="tab-users" className="text-xs">
            Users Management
          </TabsTrigger>
        </TabsList>

        <TabsContent value="teams">
          <TeamsTab />
        </TabsContent>

        <TabsContent value="users">
          <UsersTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
