import { createRoute, Outlet, redirect, useNavigate } from '@tanstack/react-router';
import { Route as rootRoute } from './__root';
import { getStoredAuth, parseTokenPayload } from '../utils/auth';
import { getSavedTheme, applyTheme, getNextTheme, type Theme } from '../utils/theme';
import { useEffect, useState } from 'react';

import {
  SidebarProvider,
  SidebarTrigger,
  SidebarInset,
} from '@/components/ui/sidebar';
import { SidebarNav } from '@/components/layout/SidebarNav';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  SunIcon,
  MoonIcon,
  MessageSquareIcon,
  FileTextIcon,
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

const navItems = [
  { id: 'chat', icon: MessageSquareIcon, label: 'Chat Console', to: '/dashboard/chat' },
  { id: 'docs', icon: FileTextIcon, label: 'Docs Console', to: '/dashboard/docs' },
];

function DashboardLayout() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState<Theme>(() => getSavedTheme());

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
        <SidebarNav
          navItems={navItems}
          userEmail={userEmail}
          userRole={userRole}
          theme={theme}
          onThemeToggle={handleToggleTheme}
          onLogout={handleLogout}
          isSuperAdmin={userRole === 'superadmin'}
        />

        <SidebarInset className="flex flex-1 flex-col overflow-hidden">
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background/80 backdrop-blur-md px-5 text-card-foreground sticky top-0 z-10">
            <div className="flex items-center gap-3">
              <SidebarTrigger className="text-foreground/60 hover:text-foreground transition-colors" />
              <Separator orientation="vertical" className="h-4 bg-border/50" />
              <h1 id="dashboard-header" className="text-sm font-semibold tracking-tight text-foreground/80">
                Dashboard
              </h1>
            </div>
            <Button
              id="theme-toggle"
              variant="ghost"
              size="icon-sm"
              onClick={handleToggleTheme}
              className="text-foreground/60 hover:text-foreground hover:bg-accent/50 transition-all duration-300"
            >
              <div className="relative size-[18px]">
                <SunIcon className={`size-[18px] absolute inset-0 transition-all duration-300 ${
                  theme === 'light' ? 'opacity-0 rotate-90 scale-0' : 'opacity-100 rotate-0 scale-100'
                }`} />
                <MoonIcon className={`size-[18px] absolute inset-0 transition-all duration-300 ${
                  theme === 'light' ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-0'
                }`} />
              </div>
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
