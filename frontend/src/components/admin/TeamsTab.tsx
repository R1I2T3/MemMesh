import { useState, useEffect, useCallback, type FormEvent } from 'react';
import { apiFetch } from '@/lib/api';
import { AlertBanner } from '@/components/shared/AlertBanner';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import { UsersIcon, PlusIcon, Loader2Icon, UserMinusIcon, Trash2Icon } from 'lucide-react';
import type { Team, User, TeamMember } from '@/types/api';

export function TeamsTab() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [selectedTeamMembers, setSelectedTeamMembers] = useState<TeamMember[]>([]);
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [newMemberUserId, setNewMemberUserId] = useState('');
  const [newMemberRole, setNewMemberRole] = useState<'member' | 'admin' | 'owner'>('member');
  const [users, setUsers] = useState<User[]>([]);
  const [teamsError, setTeamsError] = useState('');
  const [teamsSuccess, setTeamsSuccess] = useState('');
  const [membersError, setMembersError] = useState('');
  const [membersSuccess, setMembersSuccess] = useState('');

  const fetchUsers = useCallback(async () => {
    try {
      const res = await apiFetch('/api/admin/users');
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users || []);
      }
    } catch {}
  }, []);

  const fetchTeams = useCallback(async () => {
    setLoadingTeams(true);
    setTeamsError('');
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
  }, []);

  const fetchMembers = useCallback(async (teamId: string) => {
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
  }, []);

  useEffect(() => {
    fetchTeams();
    fetchUsers();
  }, [fetchTeams, fetchUsers]);

  useEffect(() => {
    if (selectedTeam) {
      fetchMembers(selectedTeam.team_id);
    } else {
      setSelectedTeamMembers([]);
    }
  }, [selectedTeam, fetchMembers]);

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
      const res = await apiFetch(`/api/admin/teams/${teamId}`, { method: 'DELETE' });
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

  const handleAddMember = async (e: FormEvent) => {
    e.preventDefault();
    setMembersError('');
    setMembersSuccess('');
    if (!selectedTeam || !newMemberUserId) return;

    try {
      const res = await apiFetch('/api/admin/members', {
        method: 'POST',
        body: JSON.stringify({ team_id: selectedTeam.team_id, user_id: newMemberUserId, role: newMemberRole }),
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
      const res = await apiFetch(`/api/admin/members?team_id=${selectedTeam.team_id}&user_id=${userId}`, { method: 'DELETE' });
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
      <div className="flex flex-col gap-6">
        <Card className="border-border/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Teams</CardTitle>
            <CardDescription className="text-[11px]">View, select, and manage active teams</CardDescription>
          </CardHeader>
          <CardContent>
            <AlertBanner type="error" message={teamsError} />
            <AlertBanner type="success" message={teamsSuccess} />

            {loadingTeams ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
                <Loader2Icon className="animate-spin h-4 w-4" />
                <span>Loading teams...</span>
              </div>
            ) : (
              <div className="overflow-x-auto border border-border/60 rounded-xl">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-[11px] font-semibold">Team Name</TableHead>
                      <TableHead className="text-right text-[11px] font-semibold">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {teams.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={2} className="text-center py-6 text-muted-foreground text-xs">
                          No teams created yet.
                        </TableCell>
                      </TableRow>
                    ) : (
                      teams.map((team) => (
                        <TableRow key={team.team_id}>
                          <TableCell className="font-medium text-xs">{team.name}</TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                variant={selectedTeam?.team_id === team.team_id ? 'default' : 'outline'}
                                size="xs"
                                id={`btn-select-team-${team.team_id}`}
                                data-testid={`select-team-${team.name}`}
                                onClick={() => setSelectedTeam(team)}
                              >
                                Members
                              </Button>
                              <Button
                                variant="destructive"
                                size="icon-xs"
                                id={`btn-delete-team-${team.team_id}`}
                                data-testid={`delete-team-${team.name}`}
                                onClick={() => handleDeleteTeam(team.team_id, team.name)}
                              >
                                <Trash2Icon className="h-3.5 w-3.5" />
                              </Button>
                            </div>
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

        <Card className="border-border/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Create Team</CardTitle>
            <CardDescription className="text-[11px]">Create a new team in the console</CardDescription>
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
                className="flex-1 h-9 text-xs"
              />
              <Button type="submit" id="team-create-submit" size="sm" className="h-9 text-xs gap-1.5">
                <PlusIcon className="h-3.5 w-3.5" />
                Create Team
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <div>
        {selectedTeam ? (
          <Card className="border-border/80 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Members of {selectedTeam.name}</CardTitle>
              <CardDescription className="text-[11px]">Manage user memberships for this team</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-6">
              <AlertBanner type="error" message={membersError} />
              <AlertBanner type="success" message={membersSuccess} />

              {loadingMembers ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
                  <Loader2Icon className="animate-spin h-4 w-4" />
                  <span>Loading members...</span>
                </div>
              ) : (
                <div className="overflow-x-auto border border-border/60 rounded-xl">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-[11px] font-semibold">User ID / Email</TableHead>
                        <TableHead className="text-[11px] font-semibold">Role</TableHead>
                        <TableHead className="text-right text-[11px] font-semibold">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedTeamMembers.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={3} className="text-center py-6 text-muted-foreground text-xs">
                            No members in this team.
                          </TableCell>
                        </TableRow>
                      ) : (
                        selectedTeamMembers.map((member) => (
                          <TableRow key={member.user_id}>
                            <TableCell className="font-medium text-xs max-w-[200px] truncate">
                              {getUserEmail(member.user_id)}
                            </TableCell>
                            <TableCell className="capitalize text-muted-foreground text-[10px]">
                              {member.role}
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="destructive"
                                size="icon-xs"
                                id={`btn-remove-member-${member.user_id}`}
                                onClick={() => handleRemoveMember(member.user_id)}
                              >
                                <UserMinusIcon className="h-3.5 w-3.5" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}

              <div className="border-t border-border/50 pt-4">
                <h4 className="text-xs font-semibold mb-3 text-foreground">Add Member to Team</h4>
                <form onSubmit={handleAddMember} className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="member-user-select" className="text-[10px] font-medium text-muted-foreground">
                        Select User
                      </label>
                      <select
                        id="member-user-select"
                        value={newMemberUserId}
                        onChange={(e) => setNewMemberUserId(e.target.value)}
                        required
                        className="flex h-9 w-full rounded-xl border border-input bg-background px-3 py-1.5 text-xs shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
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
                      <label htmlFor="member-role-select" className="text-[10px] font-medium text-muted-foreground">
                        Role
                      </label>
                      <select
                        id="member-role-select"
                        value={newMemberRole}
                        onChange={(e) => setNewMemberRole(e.target.value as 'member' | 'admin' | 'owner')}
                        required
                        className="flex h-9 w-full rounded-xl border border-input bg-background px-3 py-1.5 text-xs shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                        <option value="owner">Owner</option>
                      </select>
                    </div>
                  </div>

                  <Button type="submit" id="member-add-submit" size="sm" className="w-full mt-1 h-9 text-xs gap-1.5">
                    <PlusIcon className="h-3.5 w-3.5" />
                    Add Member
                  </Button>
                </form>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="border border-dashed border-border/60 rounded-xl p-12 text-center text-muted-foreground flex flex-col items-center justify-center gap-3 h-full min-h-[300px] bg-background/50">
            <UsersIcon className="h-8 w-8 text-muted-foreground/30" />
            <p className="text-xs">Select a team from the list to view and manage its members.</p>
          </div>
        )}
      </div>
    </div>
  );
}
