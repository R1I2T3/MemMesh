<!-- frontend/src/lib/components/Header.svelte -->
<script lang="ts">
  import { authStore, logout } from '$lib/auth';
  import { appState } from '$lib/appState.svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';

  let showTeamDropdown = $state(false);

  function handleLogout() {
    logout();
    goto('/login');
  }

  function toggleDropdown() {
    showTeamDropdown = !showTeamDropdown;
  }

  function selectTeam(teamId: string) {
    appState.activeTeamId = teamId;
    showTeamDropdown = false;
  }

  // Close dropdown on click outside
  if (typeof window !== 'undefined') {
    window.addEventListener('click', (e) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.team-switcher-container')) {
        showTeamDropdown = false;
      }
    });
  }

  const currentPath = $derived($page.url.pathname);
  const isAdmin = $derived(
    $authStore.user?.global_role === 'admin' || 
    $authStore.user?.global_role === 'superadmin'
  );
</script>

<header class="topbar">
  <div class="topbar-left">
    <a href="/dashboard" class="logo-link">
      <div class="logo-small" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="18" stroke="var(--accent)" stroke-width="2" />
          <circle cx="20" cy="14" r="4" fill="var(--accent)" />
          <circle cx="12" cy="26" r="4" fill="var(--accent)" opacity="0.7" />
          <circle cx="28" cy="26" r="4" fill="var(--accent)" opacity="0.7" />
          <line x1="20" y1="18" x2="12" y2="22" stroke="var(--accent)" stroke-width="1.5" opacity="0.5" />
          <line x1="20" y1="18" x2="28" y2="22" stroke="var(--accent)" stroke-width="1.5" opacity="0.5" />
        </svg>
      </div>
      <span class="brand">MemMesh</span>
    </a>

    <!-- Divider -->
    <div class="divider"></div>

    <!-- Active Team Switcher/Selector -->
    <div class="team-switcher-container">
      <button 
        class="team-switcher-trigger" 
        onclick={toggleDropdown} 
        aria-haspopup="listbox" 
        aria-expanded={showTeamDropdown}
        title="Switch active team"
      >
        <span class="team-badge-icon">👥</span>
        <span class="active-team-name">
          {appState.activeTeam?.name ?? 'No Active Team'}
        </span>
        <span class="arrow-down" class:rotated={showTeamDropdown}>▾</span>
      </button>

      {#if showTeamDropdown}
        <div class="team-dropdown" role="listbox">
          <div class="dropdown-header">Select Active Team</div>
          {#if appState.memberships.length === 0}
            <div class="empty-dropdown">You are not a member of any teams.</div>
          {:else}
            {#each appState.memberships as membership}
              <button
                class="dropdown-item"
                class:active={membership.team_id === appState.activeTeamId}
                onclick={() => selectTeam(membership.team_id)}
                role="option"
                aria-selected={membership.team_id === appState.activeTeamId}
              >
                <div class="item-name">{membership.name}</div>
                <div class="item-role">{membership.role}</div>
              </button>
            {/each}
          {/if}
        </div>
      {/if}
    </div>

    <!-- Admin Panel Links (Admin/Superadmin only) -->
    {#if isAdmin}
      <div class="divider"></div>
      <nav class="admin-nav" aria-label="Admin Navigation">
        <a 
          href="/admin/teams" 
          class="nav-link" 
          class:active={currentPath.startsWith('/admin/teams')}
        >
          Teams
        </a>
        <a 
          href="/admin/users" 
          class="nav-link" 
          class:active={currentPath.startsWith('/admin/users')}
        >
          Users
        </a>
      </nav>
    {/if}
  </div>

  <div class="topbar-right">
    <!-- Premium Theme Toggle -->
    <button 
      class="theme-toggle" 
      onclick={() => appState.toggleTheme()} 
      aria-label="Toggle light/dark theme"
      title="Toggle Light/Dark Theme"
    >
      {#if appState.theme === 'dark'}
        <!-- Moon Icon -->
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      {:else}
        <!-- Sun Icon -->
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
      {/if}
    </button>

    {#if $authStore.user}
      <span class="user-info">
        <span class="user-email">{$authStore.user.email}</span>
        <span class="user-role">{$authStore.user.global_role}</span>
      </span>
    {/if}
    <button class="logout-button" onclick={handleLogout} id="logout-button">
      Sign Out
    </button>
  </div>
</header>

<style>
  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-sm) var(--space-xl);
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    position: sticky;
    top: 0;
    z-index: 100;
    height: 64px;
    box-shadow: var(--shadow-sm);
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: var(--space-md);
  }

  .logo-link {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    text-decoration: none;
  }

  .brand {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  .divider {
    width: 1px;
    height: 24px;
    background: var(--border);
  }

  /* Team Switcher */
  .team-switcher-container {
    position: relative;
    display: inline-block;
  }

  .team-switcher-trigger {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    background: var(--bg);
    border: 1px solid var(--border);
    padding: 6px 14px;
    border-radius: var(--radius-full);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .team-switcher-trigger:hover {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(245, 166, 35, 0.1);
  }

  .team-badge-icon {
    font-size: 14px;
  }

  .active-team-name {
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .arrow-down {
    font-size: 10px;
    color: var(--text-muted);
    transition: transform var(--transition-fast);
  }

  .arrow-down.rotated {
    transform: rotate(180deg);
  }

  .team-dropdown {
    position: absolute;
    top: calc(100% + var(--space-xs));
    left: 0;
    width: 220px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    z-index: 200;
    padding: var(--space-xs) 0;
    animation: dropdownFade 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes dropdownFade {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .dropdown-header {
    padding: var(--space-xs) var(--space-md);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border);
    margin-bottom: var(--space-xs);
  }

  .empty-dropdown {
    padding: var(--space-md);
    font-size: var(--text-sm);
    color: var(--text-muted);
    text-align: center;
  }

  .dropdown-item {
    width: 100%;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px var(--space-md);
    background: transparent;
    border: none;
    cursor: pointer;
    font-family: var(--font-sans);
    transition: all var(--transition-fast);
  }

  .dropdown-item:hover {
    background: var(--surface-hover);
  }

  .dropdown-item.active {
    background: rgba(245, 166, 35, 0.08);
    border-left: 3px solid var(--accent);
  }

  .item-name {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text);
  }

  .item-role {
    font-size: var(--text-xs);
    color: var(--text-muted);
    text-transform: capitalize;
  }

  /* Admin Nav */
  .admin-nav {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .nav-link {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-muted);
    padding: 6px 12px;
    border-radius: var(--radius-md);
    transition: all var(--transition-fast);
  }

  .nav-link:hover {
    color: var(--text);
    background: var(--surface-hover);
  }

  .nav-link.active {
    color: var(--accent);
    background: rgba(245, 166, 35, 0.08);
    font-weight: 600;
  }

  /* Right elements */
  .topbar-right {
    display: flex;
    align-items: center;
    gap: var(--space-lg);
  }

  .theme-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: var(--radius-full);
    border: 1px solid var(--border);
    background: var(--bg);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .theme-toggle:hover {
    border-color: var(--accent);
    background: var(--surface-hover);
    transform: scale(1.05);
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .user-email {
    font-size: var(--text-sm);
    color: var(--text);
  }

  .user-role {
    font-size: var(--text-xs);
    color: var(--accent);
    background: rgba(245, 166, 35, 0.1);
    padding: 2px 8px;
    border-radius: var(--radius-full);
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.05em;
  }

  .logout-button {
    padding: var(--space-xs) var(--space-md);
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .logout-button:hover {
    border-color: var(--error);
    color: var(--error);
    background: rgba(239, 68, 68, 0.05);
  }
</style>
