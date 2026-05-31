<!-- frontend/src/routes/dashboard/doc-preview.svelte -->
<script lang="ts">
  import { authStore } from '$lib/auth';
  import { get } from 'svelte/store';
  import { PUBLIC_API_BASE } from '$env/static/public';

  const API_BASE = PUBLIC_API_BASE || 'http://127.0.0.1:8081';

  interface Doc {
    doc_id: string;
    filename: string;
    file_type: string;
    file_size: number;
    status: string;
    created_at: string;
    source?: string;
  }

  interface Props {
    doc: Doc | null;
  }

  let { doc }: Props = $props();

  let textContent = $state<string | null>(null);
  let renderedMarkdown = $state<string | null>(null);
  let isLoadingContent = $state(false);
  let contentError = $state<string | null>(null);

  // Zoom state for images
  let imageZoom = $state(1);
  let isFullscreen = $state(false);
  let imgRef = $state<HTMLImageElement | null>(null);

  function getFileExtension(doc: Doc): string {
    if (doc.file_type) return doc.file_type.toLowerCase();
    return (doc.filename.split('.').pop() ?? '').toLowerCase();
  }

  function isImage(doc: Doc): boolean {
    const ext = getFileExtension(doc);
    return ['png', 'jpg', 'jpeg', 'webp'].includes(ext);
  }

  function isPDF(doc: Doc): boolean {
    return getFileExtension(doc) === 'pdf';
  }

  function isDOCX(doc: Doc): boolean {
    const ext = getFileExtension(doc);
    return ['docx', 'doc'].includes(ext);
  }

  function isText(doc: Doc): boolean {
    return getFileExtension(doc) === 'txt';
  }

  function isMarkdown(doc: Doc): boolean {
    const ext = getFileExtension(doc);
    return ['md', 'markdown'].includes(ext);
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(dateStr: string): string {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
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

  function getFileIcon(doc: Doc): string {
    const ext = getFileExtension(doc);
    switch (ext) {
      case 'pdf': return '📄';
      case 'docx': case 'doc': return '📝';
      case 'txt': return '📃';
      case 'md': case 'markdown': return '📋';
      case 'png': case 'jpg': case 'jpeg': case 'webp': return '🖼️';
      default: return '📁';
    }
  }

  /** Minimal regex-based markdown renderer */
  function renderMarkdown(md: string): string {
    let html = md
      // Escape HTML first
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      // Code blocks (fenced)
      .replace(/```[\s\S]*?```/g, (match) => {
        const code = match.slice(3, -3).replace(/^\w*\n/, '');
        return `<pre class="md-pre"><code>${code}</code></pre>`;
      })
      // Inline code
      .replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
      // Headings
      .replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>')
      // Bold + italic
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      // Bold
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      // Italic
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/_(.+?)_/g, '<em>$1</em>')
      // Strikethrough
      .replace(/~~(.+?)~~/g, '<del>$1</del>')
      // Horizontal rule
      .replace(/^---+$/gm, '<hr class="md-hr" />')
      // Blockquote
      .replace(/^&gt; (.+)$/gm, '<blockquote class="md-blockquote">$1</blockquote>')
      // Unordered lists
      .replace(/^\* (.+)$/gm, '<li class="md-li">$1</li>')
      .replace(/^- (.+)$/gm, '<li class="md-li">$1</li>')
      // Ordered lists
      .replace(/^\d+\. (.+)$/gm, '<li class="md-li md-ordered">$1</li>')
      // Links
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="md-link">$1</a>')
      // Line breaks / paragraphs
      .replace(/\n\n+/g, '</p><p class="md-p">')
      .replace(/\n/g, '<br />');

    return `<p class="md-p">${html}</p>`;
  }

  $effect(() => {
    textContent = null;
    renderedMarkdown = null;
    contentError = null;
    imageZoom = 1;

    if (!doc) return;
    // For text/markdown files, we would fetch raw content if the endpoint exists.
    // Since no file-serving endpoint exists yet (Phase 3), show placeholder with metadata.
  });

  function zoomIn() { imageZoom = Math.min(imageZoom + 0.25, 3); }
  function zoomOut() { imageZoom = Math.max(imageZoom - 0.25, 0.25); }
  function resetZoom() { imageZoom = 1; }

  function toggleFullscreen() {
    isFullscreen = !isFullscreen;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && isFullscreen) {
      isFullscreen = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="preview-panel">
  {#if !doc}
    <!-- Empty state -->
    <div class="empty-state">
      <div class="empty-icon">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      </div>
      <h3 class="empty-title">No document selected</h3>
      <p class="empty-desc">Select a document from the list to view its details and preview.</p>
    </div>
  {:else}
    {@const ext = getFileExtension(doc)}
    {@const statusCfg = getStatusConfig(doc.status)}

    <div class="preview-content" class:fullscreen-active={isFullscreen}>
      <!-- Document header -->
      <div class="doc-header">
        <div class="doc-header-icon" aria-hidden="true">{getFileIcon(doc)}</div>
        <div class="doc-header-info">
          <h2 class="doc-title" title={doc.filename}>{doc.filename}</h2>
          <span class="status-badge {statusCfg.class}">{statusCfg.label}</span>
        </div>
      </div>

      <!-- Metadata panel -->
      <div class="metadata-panel glass-card">
        <h3 class="metadata-heading">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          Metadata
        </h3>

        <div class="metadata-grid">
          <div class="meta-row">
            <span class="meta-label">File name</span>
            <span class="meta-value filename-value" title={doc.filename}>{doc.filename}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">File type</span>
            <span class="meta-value">
              <span class="type-chip">{ext.toUpperCase()}</span>
            </span>
          </div>
          <div class="meta-row">
            <span class="meta-label">File size</span>
            <span class="meta-value">{formatFileSize(doc.file_size)}</span>
          </div>
          {#if doc.source}
            <div class="meta-row">
              <span class="meta-label">Source</span>
              <span class="meta-value">{doc.source}</span>
            </div>
          {/if}
          <div class="meta-row">
            <span class="meta-label">Uploaded</span>
            <span class="meta-value">{formatDate(doc.created_at)}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Ingestion status</span>
            <span class="meta-value status-badge {statusCfg.class}">{statusCfg.label}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Document ID</span>
            <span class="meta-value mono-value">{doc.doc_id}</span>
          </div>
        </div>
      </div>

      <!-- Preview area -->
      <div class="preview-area">
        <h3 class="preview-heading">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          Preview
        </h3>

        {#if isImage(doc)}
          <!-- Image viewer with zoom/fullscreen -->
          <div class="image-viewer-wrapper">
            <div class="image-controls">
              <button class="img-ctrl-btn" onclick={zoomOut} disabled={imageZoom <= 0.25} aria-label="Zoom out">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /><line x1="8" y1="11" x2="14" y2="11" />
                </svg>
              </button>
              <span class="zoom-level">{Math.round(imageZoom * 100)}%</span>
              <button class="img-ctrl-btn" onclick={zoomIn} disabled={imageZoom >= 3} aria-label="Zoom in">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /><line x1="11" y1="8" x2="11" y2="14" /><line x1="8" y1="11" x2="14" y2="11" />
                </svg>
              </button>
              <button class="img-ctrl-btn" onclick={resetZoom} aria-label="Reset zoom">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" />
                </svg>
              </button>
              <button class="img-ctrl-btn fullscreen-btn" onclick={toggleFullscreen} aria-label={isFullscreen ? 'Exit fullscreen' : 'View fullscreen'}>
                {#if isFullscreen}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
                  </svg>
                {:else}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
                  </svg>
                {/if}
              </button>
            </div>

            <div class="image-viewer" class:fullscreen={isFullscreen} onclick={() => { if (isFullscreen) isFullscreen = false; }}>
              <!-- Since no file-serving endpoint exists, show a placeholder image viewer -->
              <div class="image-placeholder">
                <div class="image-placeholder-icon">🖼️</div>
                <p class="image-placeholder-name">{doc.filename}</p>
                <p class="image-placeholder-desc">Image preview will be available once the file serving endpoint is configured in Phase 4.</p>
                <div class="phase-badge">Phase 4 Feature</div>
              </div>
            </div>
          </div>

        {:else if isPDF(doc)}
          <!-- PDF preview placeholder -->
          <div class="format-preview-placeholder pdf-placeholder">
            <div class="format-icon">📄</div>
            <h4>PDF Preview</h4>
            <p>PDF embedded viewer will be available once the file serving endpoint is configured.</p>
            <div class="phase-badge">Phase 4 Feature</div>
            {#if doc.status === 'indexed'}
              <div class="indexed-note">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
                This document has been indexed and is available for RAG queries.
              </div>
            {:else}
              <div class="pending-note">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                </svg>
                Preview will be available once this document is indexed.
              </div>
            {/if}
          </div>

        {:else if isDOCX(doc)}
          <!-- DOCX placeholder -->
          <div class="format-preview-placeholder docx-placeholder">
            <div class="format-icon">📝</div>
            <h4>DOCX Preview</h4>
            <p>Word document rendering will be available once the file serving endpoint is configured.</p>
            <div class="phase-badge">Phase 4 Feature</div>
            {#if doc.status === 'indexed'}
              <div class="indexed-note">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
                This document has been indexed and is available for RAG queries.
              </div>
            {:else}
              <div class="pending-note">
                Preview will be available once this document is indexed.
              </div>
            {/if}
          </div>

        {:else if isText(doc)}
          <!-- TXT placeholder — would show content if served -->
          <div class="format-preview-placeholder text-placeholder">
            <div class="format-icon">📃</div>
            <h4>Text File</h4>
            <p>Raw text content will be displayed here once the file serving endpoint is available in Phase 4.</p>
            <div class="phase-badge">Phase 4 Feature</div>
            {#if doc.status === 'indexed'}
              <div class="indexed-note">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
                This document has been indexed and is available for RAG queries.
              </div>
            {/if}
          </div>

        {:else if isMarkdown(doc)}
          <!-- Markdown placeholder — would render content if served -->
          <div class="format-preview-placeholder md-placeholder">
            <div class="format-icon">📋</div>
            <h4>Markdown Document</h4>
            <p>Rendered markdown preview will be displayed here once the file serving endpoint is available in Phase 4.</p>
            <div class="phase-badge">Phase 4 Feature</div>
            {#if doc.status === 'indexed'}
              <div class="indexed-note">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
                This document has been indexed and is searchable.
              </div>
            {/if}
          </div>

        {:else}
          <!-- Unknown format -->
          <div class="format-preview-placeholder">
            <div class="format-icon">📁</div>
            <h4>Preview Unavailable</h4>
            <p>Preview is not supported for this file type.</p>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .preview-panel {
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

  /* ===== Empty State ===== */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    padding: var(--space-2xl);
    text-align: center;
    gap: var(--space-md);
    min-height: 300px;
  }

  .empty-icon {
    color: var(--border);
    opacity: 0.6;
    animation: floatEmpty 4s ease-in-out infinite;
  }

  @keyframes floatEmpty {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    50% { transform: translateY(-8px) rotate(1deg); }
  }

  .empty-title {
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-muted);
  }

  .empty-desc {
    font-size: var(--text-sm);
    color: var(--text-muted);
    opacity: 0.7;
    max-width: 240px;
    line-height: 1.6;
  }

  /* ===== Preview content ===== */
  .preview-content {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
    animation: fadeSlideIn 0.25s ease-out;
  }

  @keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .preview-content::-webkit-scrollbar { width: 4px; }
  .preview-content::-webkit-scrollbar-track { background: transparent; }
  .preview-content::-webkit-scrollbar-thumb { background: var(--border); border-radius: var(--radius-full); }

  /* Document header */
  .doc-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-md);
    padding: var(--space-lg);
    border-bottom: 1px solid var(--border);
    background: rgba(26, 26, 31, 0.4);
    flex-shrink: 0;
  }

  .doc-header-icon {
    font-size: 2rem;
    flex-shrink: 0;
    line-height: 1;
  }

  .doc-header-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .doc-title {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Metadata panel */
  .metadata-panel {
    margin: var(--space-lg);
    border-radius: var(--radius-lg);
    padding: var(--space-lg);
    background: rgba(15, 15, 17, 0.5);
    border: 1px solid var(--border);
    flex-shrink: 0;
  }

  .glass-card {
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }

  .metadata-heading,
  .preview-heading {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    margin-bottom: var(--space-md);
  }

  .metadata-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .meta-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: var(--space-md);
    padding: var(--space-xs) 0;
    border-bottom: 1px solid rgba(45, 45, 51, 0.5);
  }

  .meta-row:last-child {
    border-bottom: none;
  }

  .meta-label {
    font-size: var(--text-xs);
    color: var(--text-muted);
    flex-shrink: 0;
    font-weight: 500;
    padding-top: 1px;
    min-width: 100px;
  }

  .meta-value {
    font-size: var(--text-sm);
    color: var(--text);
    font-weight: 500;
    text-align: right;
    word-break: break-all;
  }

  .filename-value {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--accent);
  }

  .mono-value {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-muted);
  }

  .type-chip {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    padding: 1px 7px;
    border-radius: var(--radius-full);
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-muted);
    letter-spacing: 0.03em;
  }

  /* Status badges */
  .status-badge {
    display: inline-flex;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: var(--radius-full);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid transparent;
  }

  .status-indexed { background: rgba(34, 197, 94, 0.1); color: var(--success); border-color: rgba(34, 197, 94, 0.25); }
  .status-indexing { background: rgba(59, 130, 246, 0.1); color: #60a5fa; border-color: rgba(59, 130, 246, 0.25); }
  .status-pending { background: rgba(234, 179, 8, 0.1); color: #fbbf24; border-color: rgba(234, 179, 8, 0.25); }
  .status-failed { background: rgba(239, 68, 68, 0.1); color: var(--error); border-color: rgba(239, 68, 68, 0.25); }

  /* Preview area */
  .preview-area {
    margin: 0 var(--space-lg) var(--space-lg);
    flex: 1;
  }

  /* Format placeholders */
  .format-preview-placeholder {
    border: 1px dashed var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-xl) var(--space-lg);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-md);
    text-align: center;
    background: rgba(15, 15, 17, 0.3);
    transition: border-color var(--transition-normal);
  }

  .format-preview-placeholder:hover {
    border-color: var(--accent);
  }

  .format-icon {
    font-size: 3rem;
    animation: floatIcon 3s ease-in-out infinite;
  }

  @keyframes floatIcon {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-5px); }
  }

  .format-preview-placeholder h4 {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text);
  }

  .format-preview-placeholder p {
    font-size: var(--text-sm);
    color: var(--text-muted);
    max-width: 280px;
    line-height: 1.6;
  }

  .phase-badge {
    font-size: var(--text-xs);
    font-weight: 600;
    font-family: var(--font-mono);
    padding: 3px 10px;
    border-radius: var(--radius-full);
    background: rgba(245, 166, 35, 0.08);
    color: var(--accent);
    border: 1px solid rgba(245, 166, 35, 0.2);
    letter-spacing: 0.03em;
  }

  .indexed-note,
  .pending-note {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-size: var(--text-xs);
    padding: var(--space-xs) var(--space-md);
    border-radius: var(--radius-md);
    margin-top: var(--space-xs);
  }

  .indexed-note {
    background: rgba(34, 197, 94, 0.08);
    color: var(--success);
    border: 1px solid rgba(34, 197, 94, 0.2);
  }

  .pending-note {
    background: rgba(234, 179, 8, 0.08);
    color: #fbbf24;
    border: 1px solid rgba(234, 179, 8, 0.2);
  }

  /* ===== Image Viewer ===== */
  .image-viewer-wrapper {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: rgba(15, 15, 17, 0.5);
  }

  .image-controls {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    padding: var(--space-sm) var(--space-md);
    border-bottom: 1px solid var(--border);
    background: rgba(26, 26, 31, 0.6);
  }

  .img-ctrl-btn {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
  }

  .img-ctrl-btn:hover:not(:disabled) {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(245, 166, 35, 0.06);
  }

  .img-ctrl-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .zoom-level {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-muted);
    min-width: 36px;
    text-align: center;
  }

  .fullscreen-btn {
    margin-left: auto;
  }

  .image-viewer {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-lg);
    min-height: 200px;
    overflow: hidden;
    transition: all var(--transition-normal);
  }

  .image-viewer.fullscreen {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.95);
    border-radius: 0;
    min-height: 100vh;
    cursor: zoom-out;
    backdrop-filter: blur(4px);
  }

  .image-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-md);
    text-align: center;
    padding: var(--space-xl);
  }

  .image-placeholder-icon {
    font-size: 3.5rem;
    filter: grayscale(0.3);
    animation: floatIcon 3s ease-in-out infinite;
  }

  .image-placeholder-name {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--accent);
    font-weight: 500;
  }

  .image-placeholder-desc {
    font-size: var(--text-sm);
    color: var(--text-muted);
    max-width: 260px;
    line-height: 1.6;
  }

  /* Markdown rendered content styles (for when content is available in Phase 4) */
  :global(.md-h1) { font-size: var(--text-2xl); font-weight: 700; margin: 1em 0 0.5em; color: var(--text); }
  :global(.md-h2) { font-size: var(--text-xl); font-weight: 600; margin: 1em 0 0.4em; color: var(--text); }
  :global(.md-h3) { font-size: var(--text-lg); font-weight: 600; margin: 0.8em 0 0.3em; color: var(--text); }
  :global(.md-p) { margin: 0.5em 0; line-height: 1.7; color: var(--text); }
  :global(.md-pre) { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-md); overflow-x: auto; font-family: var(--font-mono); font-size: var(--text-sm); }
  :global(.md-inline-code) { font-family: var(--font-mono); font-size: 0.85em; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 1px 5px; color: var(--accent); }
  :global(.md-blockquote) { border-left: 3px solid var(--accent); padding-left: var(--space-md); color: var(--text-muted); font-style: italic; margin: var(--space-sm) 0; }
  :global(.md-link) { color: var(--accent); text-decoration: underline; }
  :global(.md-hr) { border: none; border-top: 1px solid var(--border); margin: var(--space-lg) 0; }
  :global(.md-li) { margin-left: var(--space-lg); margin-bottom: var(--space-xs); }
</style>
