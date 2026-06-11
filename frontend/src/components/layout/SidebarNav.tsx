import { Link } from '@tanstack/react-router';
import type { LucideIcon } from 'lucide-react';
import {
  SunIcon,
  MoonIcon,
  LogOutIcon,
  UserIcon,
  LayoutDashboardIcon,
  UsersIcon,
} from 'lucide-react';
import {
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
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

interface NavItem {
  id: string;
  icon: LucideIcon;
  label: string;
  to: string;
}

interface SidebarNavProps {
  navItems: NavItem[];
  userEmail: string;
  userRole: string;
  theme: 'light' | 'dark';
  onThemeToggle: () => void;
  onLogout: () => void;
  isSuperAdmin?: boolean;
}

export function SidebarNav({
  navItems,
  userEmail,
  userRole,
  theme,
  onThemeToggle,
  onLogout,
  isSuperAdmin,
}: SidebarNavProps) {
  return (
    <Sidebar className="border-r border-border bg-sidebar text-sidebar-foreground">
      <SidebarHeader className="flex flex-col gap-2 p-4">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 p-2.5 text-white shadow-sm">
            <LayoutDashboardIcon className="size-5" />
          </div>
          <div className="flex flex-col">
            <span className="font-semibold tracking-tight text-base">MemMesh</span>
            <span className="text-[11px] text-sidebar-foreground/50 font-medium">Console Panel</span>
          </div>
        </div>
      </SidebarHeader>

      <Separator className="bg-sidebar-border/50" />

      <SidebarContent className="flex flex-col gap-4 p-3">
        <SidebarGroup>
          <SidebarGroupLabel className="px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-sidebar-foreground/40">
            Console
          </SidebarGroupLabel>
          <SidebarGroupContent className="mt-1">
            <SidebarMenu className="flex flex-col gap-0.5">
              {navItems.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    render={
                      <Link
                        id={`link-${item.id}`}
                        to={item.to}
                        activeProps={{
                          className:
                            'bg-sidebar-accent text-sidebar-accent-foreground font-medium border-l-2 border-indigo-500 dark:border-indigo-400',
                        }}
                        className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-200 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 border-l-2 border-transparent"
                      >
                        <item.icon className="size-[18px] shrink-0" />
                        <span>{item.label}</span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
              ))}
              {isSuperAdmin && (
                <>
                  <Separator className="my-1.5 bg-sidebar-border/30" />
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      render={
                        <Link
                          id="link-admin"
                          to="/dashboard/admin"
                          activeProps={{
                            className:
                              'bg-sidebar-accent text-sidebar-accent-foreground font-medium border-l-2 border-indigo-500 dark:border-indigo-400',
                          }}
                          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-200 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 border-l-2 border-transparent"
                        >
                          <UsersIcon className="size-[18px] shrink-0" />
                          <span>Admin Panel</span>
                        </Link>
                      }
                    />
                  </SidebarMenuItem>
                </>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="mt-auto flex flex-col gap-2 p-3">
        <Separator className="bg-sidebar-border/50" />
        <div className="flex items-center justify-between gap-2 rounded-lg p-2 hover:bg-sidebar-accent/30 transition-colors duration-200">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex items-center justify-center rounded-full bg-gradient-to-br from-indigo-400/20 to-indigo-600/20 p-2 text-indigo-500 dark:text-indigo-400 shrink-0">
              <UserIcon className="size-4" />
            </div>
            <div className="flex flex-col overflow-hidden min-w-0">
              <span className="truncate text-sm font-medium leading-none text-sidebar-foreground">
                {userEmail}
              </span>
              <span className="text-[11px] text-sidebar-foreground/50 capitalize mt-0.5">
                {userRole}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onThemeToggle}
              className="text-sidebar-foreground/40 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 shrink-0"
              title="Toggle theme"
            >
              {theme === 'light' ? (
                <MoonIcon className="size-[18px]" />
              ) : (
                <SunIcon className="size-[18px]" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onLogout}
              className="text-sidebar-foreground/40 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 shrink-0"
              title="Sign out"
            >
              <LogOutIcon className="size-[18px]" />
            </Button>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
