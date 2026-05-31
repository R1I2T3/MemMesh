<!-- frontend/src/routes/dashboard/doc-list.svelte -->
<script lang="ts">
  import { authStore } from '$lib/auth';
  import { get } from 'svelte/store';
  import { PUBLIC_API_BASE } from '$env/static/public';
  import { createEventDispatcher, onMount } from 'svelte';

  const API_BASE = PUBLIC_API_BASE || 'http://127.0.0.1:8081';

  interface Doc {
    doc_id: string;
    filename: string;
    file_type: string;
    file_size: number;
    status: string;
    created_at: string;
  }

  interface Props {
    teamId: string;
    refreshTrigger?: number;
  }

  let { teamId, refreshTrigger = 0 }: Props = $props();

  const dispatch = createEventDispatcher<{ select: Doc }>();

  let docs = $state<Doc[]>([]);
  let isLoading = $state(false);
  let fetchError = $state<string | null>(null);
  let selectedDocId = $state<string | null>(null);

  async function fetchDocs() {
    if (!teamId) return;
    const auth = get(authStore);
    if (!auth.accessToken) return;

    isLoading = true;
    fetchError = null;

    try {
      const response = await fetch(`${API_BASE}/team/${teamId}/docs`, {
        headers: {
          Authorization: `Bearer ${auth.accessToken}`,
        },
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to fetch documents (${response.status})`);
      }

      docs = await response.json();
    } catch (err) {
      fetchError = err instanceof Error ? err.message : 'Failed to load documents.';
      docs = [];
    } finally {
      isLoading = false;
    }
  }

  $effect(() => {
    if (teamId) fetchDocs();
  });

  $effect(() => {
    if (refreshTrigger > 0) fetchDocs();
  });

  function selectDoc(doc: Doc) {
    selectedDocId = doc.doc_id;
    dispatch('select', doc);
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(dateStr: string): string {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  }

  function getFileTypeLabel(fileType: string, filename: string): string {
    if (fileType) return fileType.toUpperCase();
    const ext = filename.split('.').pop()?.toUpperCase() ?? '—';
    return ext;
  }

  function getStatusConfig(status: string): { label: string; class: string } {
    switch (status?.toLowerCase()) {
      case 'indexed': return { label: 'Indexed', class: 'status-indexed' };
      case 'indexing': return { label: 'Indexing', class: 'status-indexing' };
      case 'pending': return { label: 'Pending', class: 'status-pending' };
      case 'failed': return { label: 'Failed', class: 'status-failed' };
      default: return { label: status ?? 'Unknown', class: 'status-pending' };
    }
  }

  function getFileIcon(fileType: string, filename: string): string {
    const ext = (fileType || filename.split('.').pop() || '').toLowerCase();
    switch (ext) {
      case 'pdf': return '📄';
      case 'docx': case 'doc': return '📝';
      case 'txt': return '📃';
      case 'md': case 'markdown': return '📋';
      case 'png': case 'jpg': case 'jpeg': case 'webp': return '🖼️';
      default: return '📁';
    }
  }
</script>

<div class="doc-list-panel">
  <div class="panel-header">
    <div class="panel-title">
      <h2>Documents</h2>
      {#if !isLoading}
        <span class="doc-count">{docs.length}</span>
      {/if}
    </div>
    <button
      class="refresh-btn"
      onclick={fetchDocs}
      disabled={isLoading}
      aria-label="Refresh document list"
      title="Refresh"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class:spinning={isLoading}
        aria-hidden="true"
      >
        <path d="M21 2v6h-6" />
        <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
        <path d="M3 22v-6h6" />
        <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      </svg>
    </button>
  </div>

  <div class="doc-list-body">
    {#if isLoading}
      <div class="state-container loading-state" aria-label="Loading documents">
        <div class="skeleton-list">
          {#each [1, 2, 3] as _}
            <div class="skeleton-item">
              <div class="skeleton-icon"></div>
              <div class="skeleton-content">
                <div class="skeleton-line wide"></div>
                <div class="skeleton-line narrow"></div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {:else if fetchError}
      <div class="state-container error-state" role="alert">
        <div class="state-icon">⚠️</div>
        <p class="state-title">Failed to load</p>
        <p class="state-desc">{fetchError}</p>
        <button class="retry-btn" onclick={fetchDocs}>Try again</button>
      </div>
    {:else if docs.length === 0}
      <div class="state-container empty-state">
        <div class="state-icon">🗂️</div>
        <p class="state-title">No documents yet</p>
        <p class="state-desc">Upload your first document using the upload zone above.</p>
      </div>
    {:else}
      <ul class="doc-items" role="listbox" aria-label="Document list">
        {#each docs as doc (doc.doc_id)}
          {@const statusCfg = getStatusConfig(doc.status)}
          <li
            class="doc-item"
            class:selected={selectedDocId === doc.doc_id}
            role="option"
            aria-selected={selectedDocId === doc.doc_id}
            tabindex="0"
            onclick={() => selectDoc(doc)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') selectDoc(doc); }}
          >
            <span class="doc-file-icon" aria-hidden="true">
              {getFileIcon(doc.file_type, doc.filename)}
            </span>

            <div class="doc-info">
              <div class="doc-name-row">
                <span class="doc-name" title={doc.filename}>{doc.filename}</span>
                <span class="doc-type-badge">{getFileTypeLabel(doc.file_type, doc.filename)}</span>
              </div>
              <div class="doc-meta-row">
                <span class="doc-meta-item">{formatFileSize(doc.file_size)}</span>
                <span class="doc-meta-sep" aria-hidden="true">·</span>
                <span class="doc-meta-item">{formatDate(doc.created_at)}</span>
              </div>
            </div>

            <span class="status-badge {statusCfg.class}" aria-label="Status: {statusCfg.label}">
              {statusCfg.label}
            </span>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</div>

<style>
  .doc-list-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: rgba(26, 26, 31, 0.5);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    overflow: hidden;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
  }

  /* Panel header */
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-lg) var(--space-lg) var(--space-md);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    background: rgba(26, 26, 31, 0.4);
  }

  .panel-title {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .panel-title h2 {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.01em;
  }

  .doc-count {
    font-size: var(--text-xs);
    font-family: var(--font-mono);
    font-weight: 600;
    background: rgba(245, 166, 35, 0.1);
    color: var(--accent);
    padding: 1px 7px;
    border-radius: var(--radius-full);
    border: 1px solid rgba(245, 166, 35, 0.2);
    min-width: 20px;
    text-align: center;
  }

  .refresh-btn {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
  }

  .refresh-btn:hover:not(:disabled) {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(245, 166, 35, 0.06);
  }

  .refresh-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .refresh-btn svg.spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Doc list body */
  .doc-list-body {
    flex: 1;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }

  .doc-list-body::-webkit-scrollbar {
    width: 4px;
  }

  .doc-list-body::-webkit-scrollbar-track {
    background: transparent;
  }

  .doc-list-body::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: var(--radius-full);
  }

  /* State containers */
  .state-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-2xl) var(--space-xl);
    text-align: center;
    gap: var(--space-sm);
    min-height: 200px;
  }

  .state-icon {
    font-size: 2.5rem;
    margin-bottom: var(--space-xs);
    animation: floatIcon 3s ease-in-out infinite;
  }

  @keyframes floatIcon {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-4px); }
  }

  .state-title {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text);
  }

  .state-desc {
    font-size: var(--text-sm);
    color: var(--text-muted);
    max-width: 220px;
    line-height: 1.5;
  }

  .retry-btn {
    margin-top: var(--space-xs);
    padding: var(--space-xs) var(--space-md);
    font-size: var(--text-sm);
    font-weight: 500;
    background: rgba(245, 166, 35, 0.1);
    color: var(--accent);
    border: 1px solid rgba(245, 166, 35, 0.25);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--transition-fast), border-color var(--transition-fast);
  }

  .retry-btn:hover {
    background: rgba(245, 166, 35, 0.18);
    border-color: var(--accent);
  }

  /* Skeleton loading */
  .skeleton-list {
    padding: var(--space-sm);
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .skeleton-item {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    padding: var(--space-md);
    border-radius: var(--radius-md);
    background: var(--surface);
  }

  .skeleton-icon {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    background: var(--surface-hover);
    animation: shimmer 1.5s ease-in-out infinite;
    flex-shrink: 0;
  }

  .skeleton-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .skeleton-line {
    height: 10px;
    border-radius: var(--radius-full);
    background: var(--surface-hover);
    animation: shimmer 1.5s ease-in-out infinite;
  }

  .skeleton-line.wide { width: 70%; }
  .skeleton-line.narrow { width: 40%; animation-delay: 0.2s; }

  @keyframes shimmer {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
  }

  /* Document items */
  .doc-items {
    list-style: none;
    padding: var(--space-sm);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .doc-item {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--transition-fast), border-color var(--transition-fast), transform var(--transition-fast);
    border: 1px solid transparent;
    position: relative;
    animation: itemAppear 0.25s ease-out both;
  }

  .doc-item:hover {
    background: var(--surface-hover);
    border-color: var(--border);
    transform: translateX(2px);
  }

  .doc-item.selected {
    background: rgba(245, 166, 35, 0.07);
    border-color: rgba(245, 166, 35, 0.3);
    box-shadow: inset 3px 0 0 var(--accent);
  }

  .doc-item.selected:hover {
    background: rgba(245, 166, 35, 0.1);
    transform: translateX(0);
  }

  @keyframes itemAppear {
    from { opacity: 0; transform: translateX(-6px); }
    to { opacity: 1; transform: translateX(0); }
  }

  .doc-file-icon {
    font-size: 1.4rem;
    flex-shrink: 0;
    width: 32px;
    text-align: center;
  }

  .doc-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .doc-name-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .doc-name {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
  }

  .doc-type-badge {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: var(--radius-full);
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-muted);
    letter-spacing: 0.03em;
    flex-shrink: 0;
  }

  .doc-meta-row {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
  }

  .doc-meta-item {
    font-size: var(--text-xs);
    color: var(--text-muted);
  }

  .doc-meta-sep {
    color: var(--border);
    font-size: var(--text-xs);
  }

  /* Status badges */
  .status-badge {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: var(--radius-full);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    flex-shrink: 0;
    border: 1px solid transparent;
  }

  .status-indexed {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
    border-color: rgba(34, 197, 94, 0.25);
  }

  .status-indexing {
    background: rgba(59, 130, 246, 0.1);
    color: #60a5fa;
    border-color: rgba(59, 130, 246, 0.25);
    animation: pulse-badge 2s ease-in-out infinite;
  }

  .status-pending {
    background: rgba(234, 179, 8, 0.1);
    color: #fbbf24;
    border-color: rgba(234, 179, 8, 0.25);
  }

  .status-failed {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
    border-color: rgba(239, 68, 68, 0.25);
  }

  @keyframes pulse-badge {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
</style>
