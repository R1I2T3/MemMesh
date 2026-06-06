<!-- frontend/src/routes/admin/users/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import type { UserListItem, Team, TeamMember } from '$lib/types';
  import Header from '$lib/components/Header.svelte';
  import { authStore } from '$lib/auth';
  import { goto } from '$app/navigation';

  let users = $state<UserListItem[]>([]);
  let teams = $state<Team[]>([]);
  let isLoading = $state(true);
  let error = $state('');

  // Map of team_id -> list of members (TeamMember)
  let allTeamMembersMap = $state<Record<string, TeamMember[]>>({});

  // Selected user for details panel
  let selectedUser = $state<UserListItem | null>(null);
  let detailError = $state('');
  let isUpdating = $state(false);

  // Add membership form state
  let selectedTeamIdToAdd = $state('');
  let selectedTeamRole = $state<'user' | 'lead'>('user');

  onMount(async () => {
    // Admin validation
    const userRole = $authStore.user?.global_role;
    if (userRole !== 'admin' && userRole !== 'superadmin') {
      goto('/dashboard');
      return;
    }

    await loadAllData();
  });

  async function loadAllData() {
    try {
      users = await api.listUsers();
      teams = await api.listTeams();

      // Load members for all teams to compute user memberships in the frontend
      const memberPromises = teams.map(async (team) => {
        try {
          const membersList = await api.listTeamMembers(team.team_id);
          allTeamMembersMap[team.team_id] = membersList;
        } catch {
          allTeamMembersMap[team.team_id] = [];
        }
      });
      await Promise.all(memberPromises);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load user and team directory';
    } finally {
      isLoading = false;
    }
  }

  // Derive the active memberships of the selected user
  const userMemberships = $derived.by(() => {
    if (!selectedUser) return [];
    const list: Array<{ team_id: string; team_name: string; role: 'user' | 'lead' }> = [];
    
    teams.forEach((team) => {
      const membersList = allTeamMembersMap[team.team_id] || [];
      const match = membersList.find((m) => m.user_id === selectedUser?.user_id);
      if (match) {
        list.push({
          team_id: team.team_id,
          team_name: team.name,
          role: match.role
        });
      }
    });

    return list;
  });

  // Derive teams the selected user is NOT a member of
  const availableTeams = $derived.by(() => {
    if (!selectedUser) return [];
    const memberships = userMemberships;
    return teams.filter((t) => !memberships.some((m) => m.team_id === t.team_id));
  });

  async function handleAddMembership(e: Event) {
    e.preventDefault();
    if (!selectedUser || !selectedTeamIdToAdd) return;
    
    detailError = '';
    isUpdating = true;
    try {
      await api.addTeamMember(selectedTeamIdToAdd, {
        user_id: selectedUser.user_id,
        role: selectedTeamRole
      });
      
      // Update local state Map to trigger reactivity
      const membersList = await api.listTeamMembers(selectedTeamIdToAdd);
      allTeamMembersMap[selectedTeamIdToAdd] = membersList;

      selectedTeamIdToAdd = '';
      selectedTeamRole = 'user';
    } catch (err) {
      detailError = err instanceof Error ? err.message : 'Failed to add user to team';
    } finally {
      isUpdating = false;
    }
  }

  async function handleRemoveMembership(teamId: string) {
    if (!selectedUser) return;
    detailError = '';
    try {
      await api.removeTeamMember(teamId, selectedUser.user_id);
      
      // Update local state map
      allTeamMembersMap[teamId] = (allTeamMembersMap[teamId] || []).filter(
        (m) => m.user_id !== selectedUser?.user_id
      );
    } catch (err) {
      detailError = err instanceof Error ? err.message : 'Failed to remove user from team';
    }
  }

  async function handleToggleTeamRole(teamId: string, currentRole: 'user' | 'lead') {
    if (!selectedUser) return;
    detailError = '';
    const nextRole = currentRole === 'lead' ? 'user' : 'lead';
    try {
      await api.addTeamMember(teamId, {
        user_id: selectedUser.user_id,
        role: nextRole
      });

      // Update local state map
      const membersList = await api.listTeamMembers(teamId);
      allTeamMembersMap[teamId] = membersList;
    } catch (err) {
      detailError = err instanceof Error ? err.message : 'Failed to update team role';
    }
  }

  function handleSelectUser(user: UserListItem) {
    selectedUser = user;
    detailError = '';
    selectedTeamIdToAdd = '';
    selectedTeamRole = 'user';
  }
</script>

<svelte:head>
  <title>Manage Users & Roles — MemMesh Admin</title>
</svelte:head>

<div class="admin-page">
  <Header />

  <main class="admin-container">
    <div class="dashboard-header">
      <div class="title-section">
        <h1>User Directory & Memberships</h1>
        <p class="subtitle">View system users and orchestrate dynamic team membership mappings.</p>
      </div>
    </div>

    {#if error}
      <div class="error-banner" role="alert">
        <span class="error-icon">⚠</span>
        {error}
      </div>
    {/if}

    {#if isLoading}
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Loading user directory...</p>
      </div>
    {:else}
      <div class="dashboard-layout">
        <!-- Users List Section -->
        <div class="directory-section glass-panel">
          <h2>System Users ({users.length})</h2>
          
          <div class="users-list">
            {#each users as user}
              <button 
                class="user-row-button" 
                class:active={selectedUser?.user_id === user.user_id}
                onclick={() => handleSelectUser(user)}
                id="user-row-{user.user_id}"
              >
                <div class="user-main-info">
                  <span class="user-icon">👤</span>
                  <div class="user-text">
                    <span class="user-email">{user.email}</span>
                    <span class="user-id-text">{user.user_id}</span>
                  </div>
                </div>
                <div class="user-meta-badges">
                  <span class="global-role-badge" class:admin={user.global_role === 'admin' || user.global_role === 'superadmin'}>
                    {user.global_role}
                  </span>
                </div>
              </button>
            {/each}
          </div>
        </div>

        <!-- Membership Controls Detail Panel -->
        <div class="controls-section">
          {#if selectedUser}
            <div class="details-panel glass-panel">
              <div class="panel-header">
                <span class="panel-icon">⚙</span>
                <div class="panel-header-text">
                  <h2>Membership Mapping</h2>
                  <p class="selected-user-email">{selectedUser.email}</p>
                </div>
              </div>

              {#if detailError}
                <div class="error-banner" role="alert">
                  <span class="error-icon">⚠</span>
                  {detailError}
                </div>
              {/if}

              <!-- Active Memberships -->
              <div class="control-group">
                <h3>Active Team Memberships ({userMemberships.length})</h3>
                
                {#if userMemberships.length === 0}
                  <div class="empty-memberships">
                    <p>This user is not mapped to any team spaces yet.</p>
                  </div>
                {:else}
                  <div class="membership-items">
                    {#each userMemberships as membership}
                      <div class="membership-item-card">
                        <div class="item-info">
                          <span class="team-bullet">■</span>
                          <div class="item-text">
                            <span class="team-name">{membership.team_name}</span>
                            <span class="team-id">{membership.team_id}</span>
                          </div>
                        </div>

                        <div class="item-controls">
                          <button 
                            class="role-toggle-badge" 
                            class:lead={membership.role === 'lead'}
                            onclick={() => handleToggleTeamRole(membership.team_id, membership.role)}
                            title="Click to toggle between Member & Team Lead"
                          >
                            {membership.role === 'lead' ? 'Team Lead 👑' : 'Member 👥'}
                          </button>
                          
                          <button 
                            class="remove-btn" 
                            onclick={() => handleRemoveMembership(membership.team_id)}
                            aria-label="Remove membership from {membership.team_name}"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>

              <!-- Add to new team -->
              <div class="control-group add-team-container">
                <h3>Map to New Team</h3>
                {#if availableTeams.length === 0}
                  <div class="empty-memberships text-center">
                    <p>This user is already mapped to all active teams.</p>
                  </div>
                {:else}
                  <form onsubmit={handleAddMembership} class="add-membership-form">
                    <div class="form-row">
                      <div class="form-field flex-2">
                        <select bind:value={selectedTeamIdToAdd} required id="team-to-add-select">
                          <option value="" disabled selected>Select a team space...</option>
                          {#each availableTeams as team}
                            <option value={team.team_id}>{team.name}</option>
                          {/each}
                        </select>
                      </div>
                      <div class="form-field flex-1">
                        <select bind:value={selectedTeamRole} id="role-to-add-select">
                          <option value="user">Member (User)</option>
                          <option value="lead">Team Lead</option>
                        </select>
                      </div>
                      <button type="submit" class="apply-btn" disabled={isUpdating} id="add-membership-submit">
                        Map User
                      </button>
                    </div>
                  </form>
                {/if}
              </div>
            </div>
          {:else}
            <div class="no-selection-panel glass-panel">
              <span class="info-large-icon">👤</span>
              <h3>No User Selected</h3>
              <p>Select a user from the directory to review, update, or authorize team-level access contexts.</p>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </main>
</div>

<style>
  .admin-page {
    min-height: 100vh;
    background: var(--bg);
  }

  .admin-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-xl) var(--space-md);
  }

  .dashboard-header {
    margin-bottom: var(--space-xl);
  }

  .title-section h1 {
    font-size: var(--text-3xl);
    font-weight: 700;
    letter-spacing: -0.03em;
  }

  .subtitle {
    color: var(--text-muted);
    font-size: var(--text-sm);
  }

  .error-banner {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--radius-md);
    color: var(--error);
    font-size: var(--text-sm);
    margin-bottom: var(--space-lg);
  }

  .error-icon {
    font-weight: bold;
  }

  .loading-state {
    text-align: center;
    padding: var(--space-2xl) var(--space-md);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto var(--space-md);
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Split layout */
  .dashboard-layout {
    display: grid;
    grid-template-columns: 1fr 1.2fr;
    gap: var(--space-lg);
    align-items: start;
  }

  @media (max-width: 900px) {
    .dashboard-layout {
      grid-template-columns: 1fr;
    }
  }

  .glass-panel {
    background: rgba(26, 26, 31, 0.4);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-xl);
    box-shadow: var(--shadow-sm);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }

  .directory-section h2 {
    font-size: var(--text-lg);
    font-weight: 700;
    margin-bottom: var(--space-lg);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--space-xs);
  }

  /* User rows list */
  .users-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    max-height: 520px;
    overflow-y: auto;
    padding-right: var(--space-xs);
  }

  .user-row-button {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px var(--space-md);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-family: var(--font-sans);
    transition: all var(--transition-fast);
    text-align: left;
  }

  .user-row-button:hover {
    border-color: var(--accent);
    background: var(--surface-hover);
    transform: translateX(2px);
  }

  .user-row-button.active {
    border-color: var(--accent);
    background: rgba(245, 166, 35, 0.08);
    box-shadow: var(--shadow-glow);
  }

  .user-main-info {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    min-width: 0;
    flex: 1;
  }

  .user-icon {
    font-size: 18px;
    color: var(--text-muted);
  }

  .user-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .user-email {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .user-id-text {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 200px;
  }

  .global-role-badge {
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
    padding: 2px 8px;
    border-radius: var(--radius-full);
    border: 1px solid var(--border);
  }

  .global-role-badge.admin {
    background: rgba(239, 68, 68, 0.08);
    color: var(--error);
    border-color: rgba(239, 68, 68, 0.15);
  }

  /* Details Panel controls */
  .controls-section {
    position: sticky;
    top: 80px;
  }

  .details-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-xl);
  }

  .panel-header {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--space-md);
  }

  .panel-icon {
    font-size: 24px;
    color: var(--accent);
  }

  .panel-header-text h2 {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--text);
  }

  .selected-user-email {
    font-size: var(--text-sm);
    color: var(--text-muted);
    font-weight: 500;
  }

  .control-group h3 {
    font-size: var(--text-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.05em;
    margin-bottom: var(--space-md);
  }

  .empty-memberships {
    padding: var(--space-lg);
    text-align: center;
    color: var(--text-muted);
    font-size: var(--text-sm);
    border: 1px dashed var(--border);
    border-radius: var(--radius-md);
    background: var(--bg);
  }

  .empty-memberships.text-center {
    text-align: center;
  }

  .membership-items {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .membership-item-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-sm) var(--space-md);
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .item-info {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    min-width: 0;
    flex: 1;
  }

  .team-bullet {
    color: var(--accent);
    font-size: 10px;
  }

  .item-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .team-name {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .team-id {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 180px;
  }

  .item-controls {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .role-toggle-badge {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
    border: 1px solid var(--border);
    padding: 2px 8px;
    border-radius: var(--radius-full);
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .role-toggle-badge:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(245, 166, 35, 0.05);
  }

  .role-toggle-badge.lead {
    background: rgba(245, 166, 35, 0.1);
    color: var(--accent);
    border-color: rgba(245, 166, 35, 0.2);
  }

  .remove-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 600;
    cursor: pointer;
    transition: color var(--transition-fast);
  }

  .remove-btn:hover {
    color: var(--error);
  }

  /* Add Membership Form */
  .add-membership-form {
    background: var(--bg);
    padding: var(--space-md);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .form-row {
    display: flex;
    gap: var(--space-sm);
  }

  .form-field select {
    width: 100%;
    padding: 10px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    outline: none;
    cursor: pointer;
  }

  .form-field select:focus {
    border-color: var(--accent);
  }

  .flex-2 {
    flex: 2;
  }

  .flex-1 {
    flex: 1.2;
  }

  .apply-btn {
    padding: 0 var(--space-lg);
    background: var(--accent);
    color: #0f0f11;
    border: none;
    border-radius: var(--radius-md);
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: var(--text-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .apply-btn:hover {
    background: var(--accent-hover);
  }

  .apply-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* No Selection Placeholder */
  .no-selection-panel {
    text-align: center;
    padding: var(--space-2xl) var(--space-lg);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 380px;
  }

  .info-large-icon {
    font-size: 48px;
    color: var(--text-muted);
    margin-bottom: var(--space-md);
    opacity: 0.4;
  }

  .no-selection-panel h3 {
    font-size: var(--text-lg);
    font-weight: 600;
    margin-bottom: var(--space-xs);
  }

  .no-selection-panel p {
    font-size: var(--text-sm);
    color: var(--text-muted);
    max-width: 320px;
    line-height: 1.5;
  }
</style>
