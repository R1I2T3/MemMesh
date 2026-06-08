import { createRoute, redirect } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { useState, useEffect, type FormEvent } from 'react';
import { apiFetch } from '../lib/api';
import { getStoredAuth } from '../utils/auth';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import { Trash2Icon, PlusIcon, UsersIcon, UserPlusIcon, Loader2Icon, UserMinusIcon } from 'lucide-react';

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

function AlertBanner({ type, message }: { type: 'error' | 'success'; message: string }) {
  if (!message) return null;
  return (
    <div
      className={`p-3 rounded-lg text-sm mb-4 transition-all duration-200 ${
        type === 'error'
          ? 'bg-destructive/10 text-destructive border border-destructive/20'
          : 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
      }`}
      role="alert"
    >
      {message}
    </div>
  );
}

function AdminPanelConsole() {
  const [teams, setTeams] = useState<Array<{ team_id: string; name: string }>>([]);
  const [users, setUsers] = useState<Array<{ user_id: string; email: string; role: string }>>([]);
  const [selectedTeam, setSelectedTeam] = useState<{ team_id: string; name: string } | null>(null);
  const [selectedTeamMembers, setSelectedTeamMembers] = useState<Array<{ team_id: string; user_id: string; role: string }>>([]);

  // Loading States
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingMembers, setLoadingMembers] = useState(false);

  // Form states
  const [newTeamName, setNewTeamName] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [newUserRole, setNewUserRole] = useState<'user' | 'admin' | 'superadmin'>('user');
  const [newMemberUserId, setNewMemberUserId] = useState('');
  const [newMemberRole, setNewMemberRole] = useState<'member' | 'admin' | 'owner'>('member');

  // Error/Success state banners
  const [teamsError, setTeamsError] = useState('');
  const [teamsSuccess, setTeamsSuccess] = useState('');
  const [membersError, setMembersError] = useState('');
  const [membersSuccess, setMembersSuccess] = useState('');
  const [usersError, setUsersError] = useState('');
  const [usersSuccess, setUsersSuccess] = useState('');

  // Fetch actions
  const fetchTeams = async () => {
    setLoadingTeams(true);
    try {
      const res = await apiFetch('/api/admin/teams');
      if (res.ok) {
        const data = await res.json();
        setTeams(data.teams || []);
      } else {
        const errData = await res.json().catch(() => ({}));
        setTeamsError(errData.detail || 'Failed to fetch teams list');
      }
    } catch {
      setTeamsError('Network error fetching teams');
    } finally {
      setLoadingTeams(false);
    }
  };

  const fetchUsers = async () => {
    setLoadingUsers(true);
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
  };

  const fetchMembers = async (teamId: string) => {
    setLoadingMembers(true);
    setMembersError('');
    try {
      const res = await apiFetch(`/api/admin/members?team_id=${teamId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedTeamMembers(data.members || []);
      } else {
        const errData = await res.json().catch(() => ({}));
        setMembersError(errData.detail || 'Failed to fetch team members');
      }
    } catch {
      setMembersError('Network error fetching team members');
    } finally {
      setLoadingMembers(false);
    }
  };

  useEffect(() => {
    fetchTeams();
    fetchUsers();
  }, []);

  useEffect(() => {
    if (selectedTeam) {
      fetchMembers(selectedTeam.team_id);
    } else {
      setSelectedTeamMembers([]);
    }
  }, [selectedTeam]);

  // CRUD Team
  const handleCreateTeam = async (e: FormEvent) => {
    e.preventDefault();
    setTeamsError('');
    setTeamsSuccess('');
    if (!newTeamName.trim()) return;

    try {
      const res = await apiFetch('/api/admin/teams', {
        method: 'POST',
        body: JSON.stringify({ name: newTeamName }),
      });
      if (res.ok) {
        setTeamsSuccess(`Team "${newTeamName}" created successfully.`);
        setNewTeamName('');
        fetchTeams();
      } else {
        const errData = await res.json().catch(() => ({}));
        setTeamsError(errData.detail || 'Failed to create team');
      }
    } catch {
      setTeamsError('Network error creating team');
    }
  };

  const handleDeleteTeam = async (teamId: string, teamName: string) => {
    if (!confirm(`Are you sure you want to delete team "${teamName}"?`)) return;
    setTeamsError('');
    setTeamsSuccess('');
    try {
      const res = await apiFetch(`/api/admin/teams/${teamId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setTeamsSuccess(`Team "${teamName}" deleted successfully.`);
        if (selectedTeam?.team_id === teamId) {
          setSelectedTeam(null);
        }
        fetchTeams();
      } else {
        const errData = await res.json().catch(() => ({}));
        setTeamsError(errData.detail || 'Failed to delete team');
      }
    } catch {
      setTeamsError('Network error deleting team');
    }
  };

  // CRUD User
  const handleCreateUser = async (e: FormEvent) => {
    e.preventDefault();
    setUsersError('');
    setUsersSuccess('');
    if (!newUserEmail.trim() || !newUserPassword.trim()) return;

    try {
      const res = await apiFetch('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          email: newUserEmail,
          password: newUserPassword,
          global_role: newUserRole,
        }),
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
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setUsersSuccess(`User "${email}" deleted successfully.`);
        fetchUsers();
        if (selectedTeam) {
          fetchMembers(selectedTeam.team_id);
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setUsersError(errData.detail || 'Failed to delete user');
      }
    } catch {
      setUsersError('Network error deleting user');
    }
  };

  // CRUD Members
  const handleAddMember = async (e: FormEvent) => {
    e.preventDefault();
    setMembersError('');
    setMembersSuccess('');
    if (!selectedTeam || !newMemberUserId) return;

    try {
      const res = await apiFetch('/api/admin/members', {
        method: 'POST',
        body: JSON.stringify({
          team_id: selectedTeam.team_id,
          user_id: newMemberUserId,
          role: newMemberRole,
        }),
      });
      if (res.ok) {
        const userObj = users.find(u => u.user_id === newMemberUserId);
        const userEmail = userObj ? userObj.email : newMemberUserId;
        setMembersSuccess(`Added "${userEmail}" to team successfully.`);
        setNewMemberUserId('');
        setNewMemberRole('member');
        fetchMembers(selectedTeam.team_id);
      } else {
        const errData = await res.json().catch(() => ({}));
        setMembersError(errData.detail || 'Failed to add member');
      }
    } catch {
      setMembersError('Network error adding member');
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!selectedTeam) return;
    const userObj = users.find(u => u.user_id === userId);
    const userEmail = userObj ? userObj.email : userId;
    if (!confirm(`Are you sure you want to remove "${userEmail}" from this team?`)) return;

    setMembersError('');
    setMembersSuccess('');
    try {
      const res = await apiFetch(`/api/admin/members?team_id=${selectedTeam.team_id}&user_id=${userId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setMembersSuccess(`Removed "${userEmail}" from team.`);
        fetchMembers(selectedTeam.team_id);
      } else {
        const errData = await res.json().catch(() => ({}));
        setMembersError(errData.detail || 'Failed to remove member');
      }
    } catch {
      setMembersError('Network error removing member');
    }
  };

  const getUserEmail = (userId: string) => {
    const found = users.find(u => u.user_id === userId);
    return found ? found.email : userId;
  };

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full">
      <h2 id="admin-title" className="text-2xl font-bold tracking-tight mb-6">
        Admin Panel Console
      </h2>

      <Tabs defaultValue="teams" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="teams" id="tab-teams">
            Teams Management
          </TabsTrigger>
          <TabsTrigger value="users" id="tab-users">
            Users Management
          </TabsTrigger>
        </TabsList>

        {/* TEAMS MANAGEMENT TAB */}
        <TabsContent value="teams">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Teams List Card & Form */}
            <div className="flex flex-col gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Teams</CardTitle>
                  <CardDescription>View, select, and manage active teams</CardDescription>
                </CardHeader>
                <CardContent>
                  <AlertBanner type="error" message={teamsError} />
                  <AlertBanner type="success" message={teamsSuccess} />

                  {loadingTeams ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-4 justify-center">
                      <Loader2Icon className="animate-spin h-4 w-4" />
                      <span>Loading teams...</span>
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Team Name</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {teams.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={2} className="text-center py-6 text-muted-foreground">
                              No teams created yet.
                            </TableCell>
                          </TableRow>
                        ) : (
                          teams.map((team) => (
                            <TableRow key={team.team_id}>
                              <TableCell className="font-medium">{team.name}</TableCell>
                              <TableCell className="text-right flex items-center justify-end gap-2">
                                <Button
                                  variant={selectedTeam?.team_id === team.team_id ? "default" : "outline"}
                                  size="sm"
                                  id={`btn-select-team-${team.team_id}`}
                                  data-testid={`select-team-${team.name}`}
                                  onClick={() => setSelectedTeam(team)}
                                >
                                  Members
                                </Button>
                                <Button
                                  variant="destructive"
                                  size="icon"
                                  id={`btn-delete-team-${team.team_id}`}
                                  data-testid={`delete-team-${team.name}`}
                                  onClick={() => handleDeleteTeam(team.team_id, team.name)}
                                >
                                  <Trash2Icon className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* Create Team Form Card */}
              <Card>
                <CardHeader>
                  <CardTitle>Create Team</CardTitle>
                  <CardDescription>Create a new team in the console</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleCreateTeam} className="flex gap-2">
                    <Input
                      id="team-name-input"
                      type="text"
                      placeholder="Enter team name..."
                      value={newTeamName}
                      onChange={(e) => setNewTeamName(e.target.value)}
                      required
                      className="flex-1"
                    />
                    <Button type="submit" id="team-create-submit">
                      <PlusIcon className="h-4 w-4 mr-2" />
                      Create Team
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </div>

            {/* Team Members List Card (only visible when a team is selected) */}
            <div>
              {selectedTeam ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Members of {selectedTeam.name}</CardTitle>
                    <CardDescription>Manage user memberships for this team</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-6">
                    <AlertBanner type="error" message={membersError} />
                    <AlertBanner type="success" message={membersSuccess} />

                    {loadingMembers ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4 justify-center">
                        <Loader2Icon className="animate-spin h-4 w-4" />
                        <span>Loading members...</span>
                      </div>
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>User ID / Email</TableHead>
                            <TableHead>Role</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {selectedTeamMembers.length === 0 ? (
                            <TableRow>
                              <TableCell colSpan={3} className="text-center py-6 text-muted-foreground">
                                No members in this team.
                              </TableCell>
                            </TableRow>
                          ) : (
                            selectedTeamMembers.map((member) => (
                              <TableRow key={member.user_id}>
                                <TableCell className="font-medium max-w-[200px] truncate">
                                  {getUserEmail(member.user_id)}
                                </TableCell>
                                <TableCell className="capitalize text-muted-foreground text-xs">
                                  {member.role}
                                </TableCell>
                                <TableCell className="text-right">
                                  <Button
                                    variant="destructive"
                                    size="icon"
                                    id={`btn-remove-member-${member.user_id}`}
                                    onClick={() => handleRemoveMember(member.user_id)}
                                  >
                                    <UserMinusIcon className="h-4 w-4" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))
                          )}
                        </TableBody>
                      </Table>
                    )}

                    <div className="border-t pt-4">
                      <h4 className="text-sm font-semibold mb-3">Add Member to Team</h4>
                      <form onSubmit={handleAddMember} className="flex flex-col gap-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div className="flex flex-col gap-1.5">
                            <label htmlFor="member-user-select" className="text-xs font-medium text-muted-foreground">
                              Select User
                            </label>
                            <select
                              id="member-user-select"
                              value={newMemberUserId}
                              onChange={(e) => setNewMemberUserId(e.target.value)}
                              required
                              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              <option value="">-- Choose User --</option>
                              {users.map((u) => (
                                <option key={u.user_id} value={u.user_id}>
                                  {u.email} ({u.role})
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="flex flex-col gap-1.5">
                            <label htmlFor="member-role-select" className="text-xs font-medium text-muted-foreground">
                              Role
                            </label>
                            <select
                              id="member-role-select"
                              value={newMemberRole}
                              onChange={(e) => setNewMemberRole(e.target.value as 'member' | 'admin' | 'owner')}
                              required
                              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              <option value="member">Member</option>
                              <option value="admin">Admin</option>
                              <option value="owner">Owner</option>
                            </select>
                          </div>
                        </div>

                        <Button type="submit" id="member-add-submit" className="w-full mt-2">
                          <PlusIcon className="h-4 w-4 mr-2" />
                          Add Member
                        </Button>
                      </form>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <div className="border border-dashed border-border rounded-xl p-12 text-center text-muted-foreground flex flex-col items-center justify-center gap-2 h-full min-h-[300px]">
                  <UsersIcon className="h-8 w-8 text-muted-foreground/50" />
                  <p>Select a team from the list to view and manage its members.</p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* USERS MANAGEMENT TAB */}
        <TabsContent value="users">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* Users List (takes 2 cols) */}
            <div className="lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle>Users</CardTitle>
                  <CardDescription>Manage user credentials and global roles</CardDescription>
                </CardHeader>
                <CardContent>
                  <AlertBanner type="error" message={usersError} />
                  <AlertBanner type="success" message={usersSuccess} />

                  {loadingUsers ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-4 justify-center">
                      <Loader2Icon className="animate-spin h-4 w-4" />
                      <span>Loading users...</span>
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>User ID</TableHead>
                          <TableHead>Email</TableHead>
                          <TableHead>Global Role</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {users.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={4} className="text-center py-6 text-muted-foreground">
                              No users available.
                            </TableCell>
                          </TableRow>
                        ) : (
                          users.map((user) => (
                            <TableRow key={user.user_id}>
                              <TableCell className="font-mono text-xs text-muted-foreground max-w-[100px] truncate">
                                {user.user_id}
                              </TableCell>
                              <TableCell className="font-medium">{user.email}</TableCell>
                              <TableCell className="capitalize text-xs text-muted-foreground">
                                {user.role}
                              </TableCell>
                              <TableCell className="text-right">
                                <Button
                                  variant="destructive"
                                  size="icon"
                                  id={`btn-delete-user-${user.user_id}`}
                                  data-testid={`delete-user-${user.email}`}
                                  onClick={() => handleDeleteUser(user.user_id, user.email)}
                                >
                                  <Trash2Icon className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Create User Form (takes 1 col) */}
            <div>
              <Card>
                <CardHeader>
                  <CardTitle>Create User</CardTitle>
                  <CardDescription>Provision a new user account</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleCreateUser} className="flex flex-col gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="user-email-input" className="text-sm font-medium">
                        Email Address
                      </label>
                      <Input
                        id="user-email-input"
                        type="email"
                        placeholder="user@example.com"
                        value={newUserEmail}
                        onChange={(e) => setNewUserEmail(e.target.value)}
                        required
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="user-password-input" className="text-sm font-medium">
                        Password
                      </label>
                      <Input
                        id="user-password-input"
                        type="password"
                        placeholder="••••••••"
                        value={newUserPassword}
                        onChange={(e) => setNewUserPassword(e.target.value)}
                        required
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="user-role-select" className="text-sm font-medium">
                        Global Role
                      </label>
                      <select
                        id="user-role-select"
                        value={newUserRole}
                        onChange={(e) => setNewUserRole(e.target.value as 'user' | 'admin' | 'superadmin')}
                        required
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                        <option value="superadmin">Superadmin</option>
                      </select>
                    </div>

                    <Button type="submit" id="user-create-submit" className="w-full mt-2">
                      <UserPlusIcon className="h-4 w-4 mr-2" />
                      Create User
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
