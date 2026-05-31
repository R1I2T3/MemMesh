<!-- frontend/src/routes/dashboard/+page.svelte -->
<script lang="ts">
  import { authStore, logout } from '$lib/auth';
  import { goto } from '$app/navigation';

  function handleLogout() {
    logout();
    goto('/login');
  }
</script>

<svelte:head>
  <title>Dashboard — MemMesh</title>
  <meta name="description" content="MemMesh Dashboard — Your knowledge base overview" />
</svelte:head>

<div class="dashboard">
  <header class="topbar">
    <div class="topbar-left">
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
    </div>

    <div class="topbar-right">
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

  <main class="dashboard-content">
    <div class="welcome-card">
      <h1>Welcome to MemMesh</h1>
      <p>Your authenticated session is active. The full dashboard will be available in Phase 2.</p>

      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">User</span>
          <span class="info-value">{$authStore.user?.email ?? '—'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Role</span>
          <span class="info-value">{$authStore.user?.global_role ?? '—'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Status</span>
          <span class="info-value status-active">Authenticated</span>
        </div>
      </div>
    </div>
  </main>
</div>

<style>
  .dashboard {
    min-height: 100vh;
    background: var(--bg);
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-sm) var(--space-xl);
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    height: 56px;
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .brand {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: var(--space-lg);
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

  .dashboard-content {
    padding: var(--space-2xl);
    max-width: 800px;
    margin: 0 auto;
  }

  .welcome-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-2xl);
    box-shadow: var(--shadow-md);
    animation: fadeIn 0.4s ease;
  }

  .welcome-card h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    margin-bottom: var(--space-sm);
  }

  .welcome-card p {
    color: var(--text-muted);
    font-size: var(--text-base);
    margin-bottom: var(--space-xl);
  }

  .info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-md);
  }

  .info-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    padding: var(--space-md);
    background: var(--bg);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
  }

  .info-label {
    font-size: var(--text-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.05em;
  }

  .info-value {
    font-size: var(--text-base);
    font-weight: 500;
    color: var(--text);
  }

  .status-active {
    color: var(--success);
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
