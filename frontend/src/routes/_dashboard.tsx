import { createRoute, Outlet, redirect, Link, useNavigate } from '@tanstack/react-router';
import { Route as rootRoute } from './__root';
import { getStoredAuth, parseTokenPayload } from '../utils/auth';
import { getSavedTheme, applyTheme, getNextTheme } from '../utils/theme';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import {
  SidebarProvider,
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarTrigger,
  SidebarInset,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  SunIcon,
  MoonIcon,
  LogOutIcon,
  MessageSquareIcon,
  FileTextIcon,
  UserIcon,
  LayoutDashboardIcon,
  UsersIcon,
} from 'lucide-react';

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
  const navigate = useNavigate();
  const [theme, setTheme] = useState(() => getSavedTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const handleToggleTheme = () => {
    setTheme((prev) => getNextTheme(prev));
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate({ to: '/' });
  };

  const auth = getStoredAuth();
  const tokenPayload = auth ? parseTokenPayload(auth.token) : null;
  const userEmail = tokenPayload?.email || 'user@memmesh.com';
  const userRole = auth?.role || 'user';

  return (
    <SidebarProvider>
      <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
        <Sidebar className="border-r border-border bg-sidebar text-sidebar-foreground">
          <SidebarHeader className="flex flex-col gap-2 p-4">
            <div className="flex items-center gap-2">
              <div className="flex items-center justify-center rounded-lg bg-primary p-2 text-primary-foreground">
                <LayoutDashboardIcon />
              </div>
              <div className="flex flex-col">
                <span className="font-semibold tracking-tight">MemMesh</span>
                <span className="text-xs text-muted-foreground">Console Panel</span>
              </div>
            </div>
          </SidebarHeader>

          <Separator className="bg-sidebar-border" />

          <SidebarContent className="flex flex-col gap-4 p-2">
            <SidebarGroup>
              <SidebarGroupLabel className="px-2 text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/60">
                Console
              </SidebarGroupLabel>
              <SidebarGroupContent className="mt-2">
                <SidebarMenu className="flex flex-col gap-1">
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link
                        id="link-chat"
                        to="/dashboard/chat"
                        activeProps={{ className: 'bg-sidebar-accent text-sidebar-accent-foreground font-medium' }}
                        className="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                      >
                        <MessageSquareIcon />
                        <span>Chat Console</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link
                        id="link-docs"
                        to="/dashboard/docs"
                        activeProps={{ className: 'bg-sidebar-accent text-sidebar-accent-foreground font-medium' }}
                        className="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                      >
                        <FileTextIcon />
                        <span>Docs Console</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  {userRole === 'superadmin' && (
                    <SidebarMenuItem>
                      <SidebarMenuButton asChild>
                        <Link
                          id="link-admin"
                          to="/dashboard/admin"
                          activeProps={{ className: 'bg-sidebar-accent text-sidebar-accent-foreground font-medium' }}
                          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                        >
                          <UsersIcon />
                          <span>Admin Panel</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>

          <SidebarFooter className="mt-auto flex flex-col gap-2 p-2">
            <Separator className="bg-sidebar-border" />
            <div className="flex items-center justify-between gap-2 p-2">
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="flex items-center justify-center rounded-full bg-muted p-2 text-muted-foreground">
                  <UserIcon />
                </div>
                <div className="flex flex-col overflow-hidden">
                  <span className="truncate text-sm font-medium leading-none text-sidebar-foreground">
                    {userEmail}
                  </span>
                  <span className="text-xs text-muted-foreground capitalize">
                    {userRole}
                  </span>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                className="text-muted-foreground hover:text-foreground"
              >
                <LogOutIcon />
              </Button>
            </div>
          </SidebarFooter>
        </Sidebar>

        <SidebarInset className="flex flex-1 flex-col overflow-hidden">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-card px-6 text-card-foreground">
            <div className="flex items-center gap-4">
              <SidebarTrigger className="text-foreground" />
              <Separator orientation="vertical" className="h-4 bg-border" />
              <h1 id="dashboard-header" className="text-lg font-semibold tracking-tight">
                Dashboard
              </h1>
            </div>
            <Button
              id="theme-toggle"
              variant="ghost"
              size="icon"
              onClick={handleToggleTheme}
              className="text-foreground"
            >
              {theme === 'light' ? <MoonIcon /> : <SunIcon />}
            </Button>
          </header>

          <main className="flex-1 overflow-y-auto bg-background p-6">
            <Outlet />
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
