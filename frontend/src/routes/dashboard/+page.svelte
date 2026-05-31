<!-- frontend/src/routes/dashboard/+page.svelte -->
<script lang="ts">
  import { authStore } from '$lib/auth';
  import { appState } from '$lib/appState.svelte';
  import Header from '$lib/components/Header.svelte';
  import UploadZone from './upload-zone.svelte';
  import DocList from './doc-list.svelte';
  import DocPreview from './doc-preview.svelte';

  // Selected document state
  let selectedDoc = $state<any | null>(null);

  // Refresh trigger — increment to tell doc-list to re-fetch
  let refreshTrigger = $state(0);

  function handleDocSelect(event: CustomEvent) {
    selectedDoc = event.detail;
  }

  function handleUploaded(event: CustomEvent) {
    // Increment to trigger doc-list refresh
    refreshTrigger += 1;
  }
</script>

<svelte:head>
  <title>Dashboard — MemMesh</title>
  <meta name="description" content="MemMesh Dashboard — Your knowledge base overview" />
</svelte:head>

<div class="dashboard">
  <Header />

  <main class="dashboard-content">
    <!-- ===== Welcome Card ===== -->
    <div class="welcome-card glass-panel">
      <div class="welcome-header">
        <h1>Welcome to MemMesh</h1>
        <p class="subtitle">Your authenticated secure session is active.</p>
      </div>

      <!-- Active Team Info Display -->
      <div class="active-team-card">
        <div class="team-card-header">
          <span class="card-icon">👥</span>
          <h2>Active Team Context</h2>
        </div>

        {#if appState.activeTeam}
          <div class="team-details">
            <div class="detail-row">
              <span class="detail-label">Team Name</span>
              <span class="detail-value highlight">{appState.activeTeam.name}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Your Role</span>
              <span class="detail-value role-badge">{appState.activeTeam.role}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Team ID</span>
              <span class="detail-value mono">{appState.activeTeam.team_id}</span>
            </div>
          </div>
        {:else}
          <div class="no-team-message">
            <p>You have not selected an active team or do not belong to any teams yet.</p>
            <p class="small">Use the Team Switcher in the topbar to select your team context.</p>
          </div>
        {/if}
      </div>

      <!-- User Info Grid -->
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Global User</span>
          <span class="info-value">{$authStore.user?.email ?? '—'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Global Role</span>
          <span class="info-value role-text">{$authStore.user?.global_role ?? '—'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Status</span>
          <span class="info-value status-active">● Active</span>
        </div>
      </div>
    </div>

    <!-- ===== Document Explorer Section ===== -->
    {#if appState.activeTeam}
      <section class="doc-explorer-section" aria-label="Document Explorer">
        <div class="section-header">
          <div class="section-title-group">
            <span class="section-icon" aria-hidden="true">🗄️</span>
            <h2 class="section-title">Document Explorer</h2>
          </div>
          <p class="section-subtitle">
            Browse, preview, and manage your team's knowledge base documents.
          </p>
        </div>

        <!-- Upload Zone — only for leads -->
        {#if appState.activeTeam.role === 'lead'}
          <div class="upload-section">
            <UploadZone
              teamId={appState.activeTeam.team_id}
              userRole={appState.activeTeam.role}
              on:uploaded={handleUploaded}
            />
          </div>
        {/if}

        <!-- Split-pane document explorer -->
        <div class="split-pane">
          <div class="pane pane-left">
            <DocList
              teamId={appState.activeTeam.team_id}
              refreshTrigger={refreshTrigger}
              on:select={handleDocSelect}
            />
          </div>
          <div class="pane pane-right">
            <DocPreview doc={selectedDoc} />
          </div>
        </div>
      </section>
    {:else}
      <div class="no-team-explorer glass-panel">
        <div class="no-team-icon" aria-hidden="true">🗄️</div>
        <h2>No Active Team</h2>
        <p>Select a team using the Team Switcher above to access the document explorer.</p>
      </div>
    {/if}
  </main>
</div>

<style>
  /* ===== Layout ===== */
  .dashboard {
    min-height: 100vh;
    background: var(--bg);
  }

  .dashboard-content {
    padding: var(--space-2xl) var(--space-md);
    max-width: 1400px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-2xl);
  }

  /* ===== Glass Panel ===== */
  .glass-panel {
    background: rgba(26, 26, 31, 0.4);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-2xl);
    box-shadow: var(--shadow-lg);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* ===== Welcome Card ===== */
  .welcome-header h1 {
    font-size: var(--text-3xl);
    font-weight: 700;
    letter-spacing: -0.03em;
    margin-bottom: var(--space-xs);
  }

  .subtitle {
    color: var(--text-muted);
    font-size: var(--text-base);
    margin-bottom: var(--space-xl);
  }

  /* Active Team Card */
  .active-team-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-lg);
    margin-bottom: var(--space-xl);
    transition: transform var(--transition-fast), border-color var(--transition-fast);
  }

  .active-team-card:hover {
    transform: translateY(-2px);
    border-color: var(--accent);
  }

  .team-card-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: var(--space-md);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--space-xs);
  }

  .card-icon {
    font-size: var(--text-xl);
  }

  .team-card-header h2 {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text);
  }

  .team-details {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .detail-label {
    font-size: var(--text-sm);
    color: var(--text-muted);
  }

  .detail-value {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text);
  }

  .detail-value.highlight {
    color: var(--accent);
    font-weight: 600;
    font-size: var(--text-base);
  }

  .detail-value.mono {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-muted);
  }

  .role-badge {
    text-transform: uppercase;
    font-size: var(--text-xs);
    font-weight: 700;
    background: rgba(245, 166, 35, 0.1);
    color: var(--accent);
    padding: 2px 8px;
    border-radius: var(--radius-full);
    letter-spacing: 0.05em;
  }

  .no-team-message {
    padding: var(--space-lg) 0;
    text-align: center;
    color: var(--text-muted);
  }

  .no-team-message p {
    margin-bottom: var(--space-xs);
  }

  .no-team-message p.small {
    font-size: var(--text-xs);
  }

  /* Info Grid */
  .info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-md);
  }

  .info-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    padding: var(--space-md);
    background: var(--surface);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    transition: border-color var(--transition-fast);
  }

  .info-item:hover {
    border-color: rgba(245, 166, 35, 0.3);
  }

  .info-label {
    font-size: var(--text-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.05em;
  }

  .info-value {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text);
  }

  .role-text {
    text-transform: capitalize;
  }

  .status-active {
    color: var(--success);
    font-weight: 600;
  }

  /* ===== Document Explorer Section ===== */
  .doc-explorer-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-lg);
    animation: fadeIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
  }

  .section-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-md);
  }

  .section-title-group {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .section-icon {
    font-size: var(--text-2xl);
  }

  .section-title {
    font-size: var(--text-2xl);
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  .section-subtitle {
    font-size: var(--text-sm);
    color: var(--text-muted);
    align-self: center;
    max-width: 340px;
    text-align: right;
  }

  /* Upload section */
  .upload-section {
    animation: fadeIn 0.3s ease-out;
  }

  /* ===== Split Pane ===== */
  .split-pane {
    display: grid;
    grid-template-columns: 380px 1fr;
    gap: var(--space-lg);
    min-height: 560px;
  }

  .pane {
    height: 560px;
    position: relative;
  }

  /* ===== No team explorer ===== */
  .no-team-explorer {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-md);
    padding: var(--space-2xl);
    text-align: center;
    min-height: 200px;
  }

  .no-team-icon {
    font-size: 3rem;
    opacity: 0.5;
  }

  .no-team-explorer h2 {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--text-muted);
  }

  .no-team-explorer p {
    font-size: var(--text-sm);
    color: var(--text-muted);
    opacity: 0.7;
    max-width: 300px;
  }

  /* ===== Animations ===== */
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* ===== Responsive ===== */

  /* Tablet: stacked layout with preview as a drawer-like element */
  @media (max-width: 900px) {
    .split-pane {
      grid-template-columns: 1fr;
      grid-template-rows: auto auto;
      min-height: auto;
    }

    .pane {
      height: 400px;
    }

    .pane-left {
      height: 340px;
    }

    .section-subtitle {
      text-align: left;
    }
  }

  /* Mobile: full-width stacked, preview below list */
  @media (max-width: 600px) {
    .dashboard-content {
      padding: var(--space-lg) var(--space-sm);
      gap: var(--space-lg);
    }

    .glass-panel {
      padding: var(--space-lg);
    }

    .split-pane {
      gap: var(--space-md);
    }

    .pane {
      height: 320px;
    }

    .pane-left {
      height: 280px;
    }

    .section-header {
      flex-direction: column;
    }

    .section-subtitle {
      text-align: left;
    }

    .section-title {
      font-size: var(--text-xl);
    }

    .welcome-header h1 {
      font-size: var(--text-2xl);
    }
  }
</style>
