import { useState, useEffect, useCallback, type FormEvent } from 'react';
import { apiFetch } from '@/lib/api';
import { AlertBanner } from '@/components/shared/AlertBanner';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import { Trash2Icon, UserPlusIcon, Loader2Icon } from 'lucide-react';
import type { User } from '@/types/api';

export function UsersTab() {
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [newUserRole, setNewUserRole] = useState<'user' | 'admin' | 'superadmin'>('user');
  const [usersError, setUsersError] = useState('');
  const [usersSuccess, setUsersSuccess] = useState('');

  const fetchUsers = useCallback(async () => {
    setLoadingUsers(true);
    setUsersError('');
    try {
      const res = await apiFetch('/api/admin/users');
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users || []);
      } else {
        const errData = await res.json().catch(() => ({}));
        setUsersError(errData.detail || 'Failed to fetch users list');
      }
    } catch {
      setUsersError('Network error fetching users');
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleCreateUser = async (e: FormEvent) => {
    e.preventDefault();
    setUsersError('');
    setUsersSuccess('');
    if (!newUserEmail.trim() || !newUserPassword.trim()) return;

    try {
      const res = await apiFetch('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify({ email: newUserEmail, password: newUserPassword, global_role: newUserRole }),
      });
      if (res.ok) {
        setUsersSuccess(`User "${newUserEmail}" created successfully.`);
        setNewUserEmail('');
        setNewUserPassword('');
        setNewUserRole('user');
        fetchUsers();
      } else {
        const errData = await res.json().catch(() => ({}));
        setUsersError(errData.detail || 'Failed to create user');
      }
    } catch {
      setUsersError('Network error creating user');
    }
  };

  const handleDeleteUser = async (userId: string, email: string) => {
    if (!confirm(`Are you sure you want to delete user "${email}"?`)) return;
    setUsersError('');
    setUsersSuccess('');
    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
      if (res.ok) {
        setUsersSuccess(`User "${email}" deleted successfully.`);
        fetchUsers();
      } else {
        const errData = await res.json().catch(() => ({}));
        setUsersError(errData.detail || 'Failed to delete user');
      }
    } catch {
      setUsersError('Network error deleting user');
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
      <div className="lg:col-span-2">
        <Card className="border-border/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Users</CardTitle>
            <CardDescription className="text-[11px]">Manage user credentials and global roles</CardDescription>
          </CardHeader>
          <CardContent>
            <AlertBanner type="error" message={usersError} />
            <AlertBanner type="success" message={usersSuccess} />

            {loadingUsers ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
                <Loader2Icon className="animate-spin h-4 w-4" />
                <span>Loading users...</span>
              </div>
            ) : (
              <div className="overflow-x-auto border border-border/60 rounded-xl">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-[11px] font-semibold">User ID</TableHead>
                      <TableHead className="text-[11px] font-semibold">Email</TableHead>
                      <TableHead className="text-[11px] font-semibold">Global Role</TableHead>
                      <TableHead className="text-right text-[11px] font-semibold">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center py-6 text-muted-foreground text-xs">
                          No users available.
                        </TableCell>
                      </TableRow>
                    ) : (
                      users.map((user) => (
                        <TableRow key={user.user_id}>
                          <TableCell className="font-mono text-[10px] text-muted-foreground max-w-[100px] truncate">
                            {user.user_id}
                          </TableCell>
                          <TableCell className="font-medium text-xs">{user.email}</TableCell>
                          <TableCell className="capitalize text-[10px] text-muted-foreground">
                            {user.role}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="destructive"
                              size="icon-xs"
                              id={`btn-delete-user-${user.user_id}`}
                              data-testid={`delete-user-${user.email}`}
                              onClick={() => handleDeleteUser(user.user_id, user.email)}
                            >
                              <Trash2Icon className="h-3.5 w-3.5" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div>
        <Card className="border-border/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Create User</CardTitle>
            <CardDescription className="text-[11px]">Provision a new user account</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateUser} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="user-email-input" className="text-xs font-medium text-foreground/80">
                  Email Address
                </label>
                <Input
                  id="user-email-input"
                  type="email"
                  placeholder="user@example.com"
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  required
                  className="h-9 text-xs"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="user-password-input" className="text-xs font-medium text-foreground/80">
                  Password
                </label>
                <Input
                  id="user-password-input"
                  type="password"
                  placeholder="••••••••"
                  value={newUserPassword}
                  onChange={(e) => setNewUserPassword(e.target.value)}
                  required
                  className="h-9 text-xs"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="user-role-select" className="text-xs font-medium text-foreground/80">
                  Global Role
                </label>
                <select
                  id="user-role-select"
                  value={newUserRole}
                  onChange={(e) => setNewUserRole(e.target.value as 'user' | 'admin' | 'superadmin')}
                  required
                  className="flex h-9 w-full rounded-xl border border-input bg-background px-3 py-1.5 text-xs shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="superadmin">Superadmin</option>
                </select>
              </div>

              <Button type="submit" id="user-create-submit" size="sm" className="w-full mt-1 h-9 text-xs gap-1.5">
                <UserPlusIcon className="h-3.5 w-3.5" />
                Create User
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
