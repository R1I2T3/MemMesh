<!-- frontend/src/routes/admin/teams/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import type { Team, TeamMember, UserListItem } from '$lib/types';
  import Header from '$lib/components/Header.svelte';
  import { authStore } from '$lib/auth';
  import { goto } from '$app/navigation';

  let teams = $state<Team[]>([]);
  let isLoading = $state(true);
  let error = $state('');

  // Dialog state
  let showCreateDialog = $state(false);
  let newTeamName = $state('');
  let newTeamDescription = $state('');
  let createError = $state('');
  let isCreating = $state(false);

  // Drawer state for members
  let selectedTeam = $state<Team | null>(null);
  let members = $state<TeamMember[]>([]);
  let usersList = $state<UserListItem[]>([]);
  let isLoadingMembers = $state(false);
  let memberError = $state('');

  // Add member state
  let selectedUserIdToAdd = $state('');
  let selectedMemberRole = $state<'user' | 'lead'>('user');

  onMount(async () => {
    // Basic global role check
    const userRole = $authStore.user?.global_role;
    if (userRole !== 'admin' && userRole !== 'superadmin') {
      goto('/dashboard');
      return;
    }

    try {
      teams = await api.listTeams();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load teams';
    } finally {
      isLoading = false;
    }
  });

  async function openManageMembers(team: Team) {
    selectedTeam = team;
    isLoadingMembers = true;
    memberError = '';
    selectedUserIdToAdd = '';
    selectedMemberRole = 'user';
    try {
      members = await api.listTeamMembers(team.team_id);
      usersList = await api.listUsers();
    } catch (err) {
      memberError = err instanceof Error ? err.message : 'Failed to load members';
    } finally {
      isLoadingMembers = false;
    }
  }

  function closeManageMembers() {
    selectedTeam = null;
  }

  async function handleDeleteTeam(teamId: string) {
    if (!confirm('Are you sure you want to delete this team? All per-team memberships will be permanently deleted.')) {
      return;
    }
    try {
      await api.deleteTeam(teamId);
      teams = teams.filter((t) => t.team_id !== teamId);
      if (selectedTeam?.team_id === teamId) {
        selectedTeam = null;
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete team');
    }
  }

  async function handleCreateTeam(e: Event) {
    e.preventDefault();
    createError = '';
    
    const trimmedName = newTeamName.trim();
    if (!trimmedName) {
      createError = 'Team name cannot be empty or whitespace only';
      return;
    }

    isCreating = true;
    try {
      const created = await api.createTeam({
        name: trimmedName,
        description: newTeamDescription.trim() || null
      });
      teams = [created, ...teams];
      showCreateDialog = false;
      newTeamName = '';
      newTeamDescription = '';
    } catch (err) {
      createError = err instanceof Error ? err.message : 'Failed to create team';
    } finally {
      isCreating = false;
    }
  }

  async function handleAddMember(e: Event) {
    e.preventDefault();
    memberError = '';
    
    if (!selectedUserIdToAdd) {
      memberError = 'Please select a user to add';
      return;
    }
    if (!selectedTeam) return;

    try {
      await api.addTeamMember(selectedTeam.team_id, {
        user_id: selectedUserIdToAdd,
        role: selectedMemberRole
      });
      // Refetch members
      members = await api.listTeamMembers(selectedTeam.team_id);
      selectedUserIdToAdd = '';
      selectedMemberRole = 'user';
    } catch (err) {
      memberError = err instanceof Error ? err.message : 'Failed to add member';
    }
  }

  async function handleRemoveMember(userId: string) {
    if (!selectedTeam) return;
    try {
      await api.removeTeamMember(selectedTeam.team_id, userId);
      members = members.filter((m) => m.user_id !== userId);
    } catch (err) {
      memberError = err instanceof Error ? err.message : 'Failed to remove member';
    }
  }

  // Promote / Demote per-team role
  async function handleToggleRole(member: TeamMember) {
    if (!selectedTeam) return;
    const nextRole = member.role === 'lead' ? 'user' : 'lead';
    try {
      await api.addTeamMember(selectedTeam.team_id, {
        user_id: member.user_id,
        role: nextRole
      });
      // Update local state
      members = members.map((m) => m.user_id === member.user_id ? { ...m, role: nextRole } : m);
    } catch (err) {
      memberError = err instanceof Error ? err.message : 'Failed to update member role';
    }
  }

  // Filter out users who are already members of the current team
  const availableUsers = $derived(
    usersList.filter((u) => !members.some((m) => m.user_id === u.user_id))
  );
</script>

<svelte:head>
  <title>Manage Teams — MemMesh Admin</title>
</svelte:head>

<div class="admin-page">
  <Header />

  <main class="admin-container">
    <div class="dashboard-header">
      <div class="title-section">
        <h1>Teams Management</h1>
        <p class="subtitle">Create and manage tenant-level team spaces and assign workspace moderators.</p>
      </div>
      <button class="create-button" onclick={() => showCreateDialog = true} id="create-team-trigger">
        <span class="plus-icon">+</span> Create Team
      </button>
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
        <p>Loading teams...</p>
      </div>
    {:else if teams.length === 0}
      <div class="empty-state">
        <div class="empty-icon">👥</div>
        <h3>No teams found</h3>
        <p>Get started by creating your very first administrative team workspace.</p>
        <button class="create-button" onclick={() => showCreateDialog = true}>
          Create First Team
        </button>
      </div>
    {:else}
      <div class="teams-grid">
        {#each teams as team}
          <div class="team-card glass-panel" id="team-card-{team.team_id}">
            <div class="team-card-body">
              <h2 class="team-title">{team.name}</h2>
              <p class="team-desc">{team.description ?? 'No description provided.'}</p>
              <div class="team-meta">
                <span class="meta-label">Created:</span>
                <span class="meta-value">{new Date(team.created_at).toLocaleDateString()}</span>
              </div>
            </div>
            <div class="team-card-actions">
              <button 
                class="action-button primary" 
                onclick={() => openManageMembers(team)}
                id="manage-members-{team.team_id}"
              >
                Manage Members
              </button>
              <button 
                class="action-button danger" 
                onclick={() => handleDeleteTeam(team.team_id)}
                id="delete-team-{team.team_id}"
              >
                Delete
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </main>

  <!-- Create Team Modal (Overlay) -->
  {#if showCreateDialog}
    <div class="modal-backdrop" onclick={() => showCreateDialog = false} role="presentation">
      <div class="modal-content glass-panel" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="modal-header">
          <h2 id="modal-title">Create New Team</h2>
          <button class="close-modal" onclick={() => showCreateDialog = false} aria-label="Close dialog">×</button>
        </div>

        <form onsubmit={handleCreateTeam} class="modal-form">
          {#if createError}
            <div class="error-banner" role="alert">
              <span class="error-icon">⚠</span>
              {createError}
            </div>
          {/if}

          <div class="form-field">
            <label for="teamName">Team Name <span class="required">*</span></label>
            <input 
              id="teamName"
              type="text" 
              bind:value={newTeamName} 
              placeholder="e.g. Engineering, Research, Alpha Squad" 
              required
              disabled={isCreating}
              autocomplete="off"
            />
          </div>

          <div class="form-field">
            <label for="teamDesc">Description</label>
            <textarea 
              id="teamDesc"
              bind:value={newTeamDescription} 
              placeholder="Provide a brief summary of this team space..." 
              rows="3"
              disabled={isCreating}
            ></textarea>
          </div>

          <div class="modal-actions">
            <button type="button" class="action-button secondary" onclick={() => showCreateDialog = false} disabled={isCreating}>
              Cancel
            </button>
            <button type="submit" class="action-button primary" disabled={isCreating} id="create-team-submit">
              {#if isCreating}Creating...{:else}Create Team{/if}
            </button>
          </div>
        </form>
      </div>
    </div>
  {/if}

  <!-- Manage Members Drawer (Slide-out panel) -->
  {#if selectedTeam}
    <div class="drawer-backdrop" onclick={closeManageMembers} role="presentation">
      <div class="drawer-content" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <div class="drawer-header">
          <div class="drawer-title-group">
            <span class="drawer-pretitle">Manage Members</span>
            <h2 id="drawer-title">{selectedTeam.name}</h2>
          </div>
          <button class="close-drawer" onclick={closeManageMembers} aria-label="Close drawer">×</button>
        </div>

        <div class="drawer-body">
          <!-- Member Error Banner -->
          {#if memberError}
            <div class="error-banner" role="alert">
              <span class="error-icon">⚠</span>
              {memberError}
            </div>
          {/if}

          <!-- Add Member Form -->
          <div class="drawer-section">
            <h3>Add New Member</h3>
            <form onsubmit={handleAddMember} class="add-member-form">
              <div class="add-member-grid">
                <div class="select-field">
                  <select bind:value={selectedUserIdToAdd} id="user-to-add-select">
                    <option value="" disabled selected>Select user email...</option>
                    {#each availableUsers as user}
                      <option value={user.user_id}>{user.email} ({user.global_role})</option>
                    {/each}
                  </select>
                </div>
                <div class="select-field small">
                  <select bind:value={selectedMemberRole} id="role-to-add-select">
                    <option value="user">Member (User)</option>
                    <option value="lead">Team Lead</option>
                  </select>
                </div>
                <button type="submit" class="add-member-button" id="add-member-submit">Add</button>
              </div>
            </form>
          </div>

          <!-- Members List -->
          <div class="drawer-section">
            <h3>Team Members ({members.length})</h3>
            {#if isLoadingMembers}
              <div class="drawer-loading">
                <div class="spinner"></div>
                <p>Loading members...</p>
              </div>
            {:else if members.length === 0}
              <div class="drawer-empty">
                <p>No members belong to this team yet. Use the tool above to add members.</p>
              </div>
            {:else}
              <div class="members-list">
                {#each members as member}
                  <div class="member-item">
                    <div class="member-details">
                      <span class="member-email">{member.email}</span>
                      <button 
                        class="member-role-badge" 
                        class:lead={member.role === 'lead'}
                        onclick={() => handleToggleRole(member)}
                        title="Click to toggle between Member & Team Lead"
                      >
                        {member.role === 'lead' ? 'Team Lead 👑' : 'Member 👥'}
                      </button>
                    </div>
                    <button 
                      class="remove-member-button" 
                      onclick={() => handleRemoveMember(member.user_id)}
                      aria-label="Remove {member.email} from team"
                    >
                      Remove
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      </div>
    </div>
  {/if}
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
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-xl);
    gap: var(--space-md);
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

  .create-button {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    background: var(--accent);
    color: #0f0f11;
    border: none;
    padding: 10px var(--space-lg);
    border-radius: var(--radius-md);
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: var(--text-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .create-button:hover {
    background: var(--accent-hover);
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow);
  }

  .plus-icon {
    font-size: var(--text-lg);
    line-height: 1;
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

  .loading-state, .empty-state {
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

  .empty-icon {
    font-size: var(--text-3xl);
    margin-bottom: var(--space-sm);
  }

  .empty-state h3 {
    font-size: var(--text-xl);
    margin-bottom: var(--space-xs);
  }

  .empty-state p {
    color: var(--text-muted);
    font-size: var(--text-sm);
    max-width: 400px;
    margin: 0 auto var(--space-lg);
  }

  /* Teams Grid */
  .teams-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: var(--space-lg);
  }

  .team-card {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 200px;
    background: rgba(26, 26, 31, 0.4);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    transition: transform var(--transition-normal), border-color var(--transition-normal), box-shadow var(--transition-normal);
  }

  .team-card:hover {
    transform: translateY(-3px);
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
  }

  .team-card-body {
    padding: var(--space-lg);
  }

  .team-title {
    font-size: var(--text-lg);
    font-weight: 700;
    margin-bottom: var(--space-xs);
    color: var(--text);
  }

  .team-desc {
    font-size: var(--text-sm);
    color: var(--text-muted);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    height: 40px;
    margin-bottom: var(--space-sm);
  }

  .team-meta {
    font-size: var(--text-xs);
    color: var(--text-muted);
    display: flex;
    gap: var(--space-xs);
  }

  .meta-value {
    color: var(--text);
    font-weight: 500;
  }

  .team-card-actions {
    display: flex;
    border-top: 1px solid var(--border);
    background: rgba(15, 15, 17, 0.3);
  }

  .action-button {
    flex: 1;
    padding: var(--space-sm);
    border: none;
    background: transparent;
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
    text-align: center;
  }

  .action-button.primary {
    color: var(--accent);
    border-right: 1px solid var(--border);
  }

  .action-button.primary:hover {
    background: rgba(245, 166, 35, 0.05);
  }

  .action-button.danger {
    color: var(--text-muted);
  }

  .action-button.danger:hover {
    color: var(--error);
    background: rgba(239, 68, 68, 0.05);
  }

  .action-button.secondary {
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .action-button.secondary:hover {
    color: var(--text);
    background: var(--surface-hover);
  }

  /* Modals and Backdrops */
  .modal-backdrop, .drawer-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    z-index: 500;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeInBg 0.2s ease;
  }

  @keyframes fadeInBg {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .modal-content {
    width: 100%;
    max-width: 500px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-xl);
    box-shadow: var(--shadow-lg);
    animation: scaleIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  }

  @keyframes scaleIn {
    from { transform: scale(0.95); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-lg);
  }

  .close-modal, .close-drawer {
    background: transparent;
    border: none;
    font-size: 24px;
    color: var(--text-muted);
    cursor: pointer;
    transition: color var(--transition-fast);
  }

  .close-modal:hover, .close-drawer:hover {
    color: var(--text);
  }

  .modal-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .form-field label {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-muted);
  }

  .required {
    color: var(--error);
  }

  .form-field input, .form-field textarea {
    padding: 10px var(--space-md);
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: var(--text-base);
    outline: none;
    transition: border-color var(--transition-fast);
  }

  .form-field input:focus, .form-field textarea:focus {
    border-color: var(--accent);
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-md);
    margin-top: var(--space-md);
  }

  /* Drawer (Slide-out) */
  .drawer-content {
    position: absolute;
    top: 0;
    right: 0;
    width: 100%;
    max-width: 500px;
    height: 100%;
    background: var(--surface);
    border-left: 1px solid var(--border);
    box-shadow: var(--shadow-lg);
    display: flex;
    flex-direction: column;
    animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes slideIn {
    from { transform: translateX(100%); }
    to { transform: translateX(0); }
  }

  .drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-lg);
    border-bottom: 1px solid var(--border);
  }

  .drawer-title-group {
    display: flex;
    flex-direction: column;
  }

  .drawer-pretitle {
    font-size: var(--text-xs);
    color: var(--accent);
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.05em;
  }

  .drawer-header h2 {
    font-size: var(--text-xl);
    font-weight: 700;
  }

  .drawer-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-lg);
    display: flex;
    flex-direction: column;
    gap: var(--space-xl);
  }

  .drawer-section h3 {
    font-size: var(--text-sm);
    color: var(--text-muted);
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.05em;
    margin-bottom: var(--space-md);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--space-xs);
  }

  /* Add Member Form Inside Drawer */
  .add-member-form {
    background: var(--bg);
    padding: var(--space-md);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
  }

  .add-member-grid {
    display: flex;
    gap: var(--space-sm);
  }

  .select-field {
    flex: 2;
  }

  .select-field.small {
    flex: 1.2;
  }

  .select-field select {
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

  .select-field select:focus {
    border-color: var(--accent);
  }

  .add-member-button {
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

  .add-member-button:hover {
    background: var(--accent-hover);
  }

  /* Members List */
  .members-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .member-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-sm) var(--space-md);
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .member-details {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    flex: 1;
    min-width: 0;
  }

  .member-email {
    font-size: var(--text-sm);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 220px;
  }

  .member-role-badge {
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

  .member-role-badge:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(245, 166, 35, 0.05);
  }

  .member-role-badge.lead {
    background: rgba(245, 166, 35, 0.1);
    color: var(--accent);
    border-color: rgba(245, 166, 35, 0.2);
  }

  .remove-member-button {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: var(--text-xs);
    font-weight: 600;
    cursor: pointer;
    transition: color var(--transition-fast);
  }

  .remove-member-button:hover {
    color: var(--error);
  }

  .drawer-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-lg) 0;
  }

  .drawer-empty {
    padding: var(--space-lg);
    text-align: center;
    color: var(--text-muted);
    font-size: var(--text-sm);
    border: 1px dashed var(--border);
    border-radius: var(--radius-md);
  }
</style>
