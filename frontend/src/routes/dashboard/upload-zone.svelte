<!-- frontend/src/routes/dashboard/upload-zone.svelte -->
<script lang="ts">
  import { authStore } from '$lib/auth';
  import { get } from 'svelte/store';
  import { PUBLIC_API_BASE } from '$env/static/public';
  import { createEventDispatcher } from 'svelte';

  const API_BASE = PUBLIC_API_BASE || 'http://127.0.0.1:8081';

  interface Props {
    teamId: string;
    userRole: string;
  }

  let { teamId, userRole }: Props = $props();

  const dispatch = createEventDispatcher<{ uploaded: { doc_id: string; filename: string; status: string } }>();

  let isDragging = $state(false);
  let isUploading = $state(false);
  let uploadProgress = $state(0);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let fileInputRef = $state<HTMLInputElement | null>(null);
  let dragCounter = $state(0);

  const ACCEPTED_TYPES = '.pdf,.txt,.md,.docx,.png,.jpg,.jpeg,.webp';
  const ACCEPTED_MIME = [
    'application/pdf',
    'text/plain',
    'text/markdown',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/png',
    'image/jpeg',
    'image/webp',
  ];

  function formatFileType(file: File): string {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    return ext.toUpperCase();
  }

  function isValidFile(file: File): boolean {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    return ['pdf', 'txt', 'md', 'docx', 'png', 'jpg', 'jpeg', 'webp'].includes(ext);
  }

  function handleDragEnter(e: DragEvent) {
    e.preventDefault();
    dragCounter++;
    isDragging = true;
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    dragCounter--;
    if (dragCounter === 0) isDragging = false;
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    e.dataTransfer!.dropEffect = 'copy';
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    isDragging = false;
    dragCounter = 0;
    error = null;
    success = null;

    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length === 0) return;

    const file = files[0];
    if (!isValidFile(file)) {
      error = `File type not supported. Accepted: PDF, TXT, MD, DOCX, PNG, JPG, JPEG, WEBP`;
      return;
    }

    uploadFile(file);
  }

  function handleFileInput(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    error = null;
    success = null;
    uploadFile(file);
    input.value = '';
  }

  async function uploadFile(file: File) {
    if (isUploading) return;
    if (!teamId) {
      error = 'No active team selected.';
      return;
    }

    const auth = get(authStore);
    if (!auth.accessToken) {
      error = 'Not authenticated.';
      return;
    }

    isUploading = true;
    uploadProgress = 0;
    error = null;
    success = null;

    // Simulate progress with XMLHttpRequest for real progress tracking
    return new Promise<void>((resolve) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          uploadProgress = Math.round((e.loaded / e.total) * 90);
        }
      });

      xhr.addEventListener('load', () => {
        uploadProgress = 100;
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            success = `"${file.name}" uploaded successfully!`;
            dispatch('uploaded', data);
          } catch {
            success = `"${file.name}" uploaded successfully!`;
            dispatch('uploaded', { doc_id: '', filename: file.name, status: 'pending' });
          }
        } else {
          try {
            const errData = JSON.parse(xhr.responseText);
            error = errData.detail || `Upload failed (${xhr.status})`;
          } catch {
            error = `Upload failed (${xhr.status})`;
          }
        }
        isUploading = false;
        setTimeout(() => {
          uploadProgress = 0;
          if (success) setTimeout(() => { success = null; }, 3000);
        }, 800);
        resolve();
      });

      xhr.addEventListener('error', () => {
        error = 'Network error during upload.';
        isUploading = false;
        uploadProgress = 0;
        resolve();
      });

      xhr.open('POST', `${API_BASE}/team/${teamId}/ingest/upload`);
      xhr.setRequestHeader('Authorization', `Bearer ${auth.accessToken}`);
      xhr.send(formData);
    });
  }

  function openFilePicker() {
    fileInputRef?.click();
  }
</script>

{#if userRole === 'lead'}
  <div class="upload-zone-wrapper">
    <div
      class="upload-zone"
      class:dragging={isDragging}
      class:uploading={isUploading}
      role="button"
      tabindex="0"
      aria-label="Upload document — drag and drop or click to browse"
      ondragenter={handleDragEnter}
      ondragleave={handleDragLeave}
      ondragover={handleDragOver}
      ondrop={handleDrop}
      onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') openFilePicker(); }}
      onclick={openFilePicker}
    >
      <input
        bind:this={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        class="file-input-hidden"
        onchange={handleFileInput}
        tabindex="-1"
        aria-hidden="true"
      />

      <div class="upload-zone-content">
        <!-- Animated upload icon -->
        <div class="upload-icon" class:dragging={isDragging}>
          {#if isUploading}
            <div class="spinner"></div>
          {:else}
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          {/if}
        </div>

        <div class="upload-text">
          {#if isUploading}
            <p class="upload-primary">Uploading...</p>
            <p class="upload-secondary">Please wait while we process your file</p>
          {:else if isDragging}
            <p class="upload-primary">Drop your file here</p>
            <p class="upload-secondary">Release to start uploading</p>
          {:else}
            <p class="upload-primary">Drag & drop a file here</p>
            <p class="upload-secondary">or <span class="browse-link">click to browse</span></p>
          {/if}
        </div>

        <div class="accepted-types">
          {#each ['PDF', 'DOCX', 'TXT', 'MD', 'PNG', 'JPG', 'WEBP'] as ext}
            <span class="type-chip">{ext}</span>
          {/each}
        </div>
      </div>

      <!-- Progress bar -->
      {#if isUploading || uploadProgress > 0}
        <div class="progress-bar-track" role="progressbar" aria-valuenow={uploadProgress} aria-valuemin={0} aria-valuemax={100} aria-label="Upload progress">
          <div class="progress-bar-fill" style="width: {uploadProgress}%"></div>
        </div>
        <div class="progress-label">{uploadProgress}%</div>
      {/if}
    </div>

    <!-- Feedback messages -->
    {#if error}
      <div class="feedback-message error" role="alert">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        {error}
      </div>
    {/if}

    {#if success}
      <div class="feedback-message success" role="status">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <polyline points="9 12 11 14 15 10" />
        </svg>
        {success}
      </div>
    {/if}
  </div>
{/if}

<style>
  .upload-zone-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }

  .upload-zone {
    position: relative;
    border: 2px dashed var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-xl) var(--space-lg);
    cursor: pointer;
    transition:
      border-color var(--transition-normal),
      background var(--transition-normal),
      box-shadow var(--transition-normal),
      transform var(--transition-fast);
    background: transparent;
    overflow: hidden;
    text-align: center;
    outline: none;

    /* Animated dashed border via background-image */
    background-image: none;
  }

  .upload-zone::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: var(--radius-lg);
    background: transparent;
    transition: background var(--transition-normal);
    pointer-events: none;
    z-index: 0;
  }

  .upload-zone:hover,
  .upload-zone:focus-visible {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(245, 166, 35, 0.08), var(--shadow-glow);
    transform: translateY(-1px);
  }

  .upload-zone:hover::before,
  .upload-zone:focus-visible::before {
    background: rgba(245, 166, 35, 0.03);
  }

  .upload-zone.dragging {
    border-color: var(--accent);
    border-style: dashed;
    box-shadow: 0 0 0 4px rgba(245, 166, 35, 0.12), var(--shadow-glow);
    transform: scale(1.005);
    animation: dash-pulse 1.2s linear infinite;
  }

  .upload-zone.dragging::before {
    background: rgba(245, 166, 35, 0.06);
  }

  .upload-zone.uploading {
    border-color: var(--accent);
    border-style: solid;
    cursor: not-allowed;
    pointer-events: none;
  }

  @keyframes dash-pulse {
    0%, 100% { box-shadow: 0 0 0 4px rgba(245, 166, 35, 0.12), 0 0 16px rgba(245, 166, 35, 0.1); }
    50% { box-shadow: 0 0 0 6px rgba(245, 166, 35, 0.2), 0 0 28px rgba(245, 166, 35, 0.18); }
  }

  .upload-zone-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-md);
    position: relative;
    z-index: 1;
  }

  .upload-icon {
    color: var(--text-muted);
    transition: color var(--transition-normal), transform var(--transition-normal);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    background: var(--surface);
    border-radius: var(--radius-full);
    border: 1px solid var(--border);
  }

  .upload-icon.dragging {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(245, 166, 35, 0.08);
    transform: translateY(-4px) scale(1.08);
  }

  .upload-zone:hover .upload-icon:not(.dragging) {
    color: var(--accent);
    border-color: var(--accent);
    transform: translateY(-2px);
  }

  .upload-text {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .upload-primary {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text);
  }

  .upload-secondary {
    font-size: var(--text-sm);
    color: var(--text-muted);
  }

  .browse-link {
    color: var(--accent);
    font-weight: 500;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .accepted-types {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    justify-content: center;
    margin-top: var(--space-xs);
  }

  .type-chip {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: 2px 8px;
    border-radius: var(--radius-full);
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-muted);
    letter-spacing: 0.03em;
    transition: color var(--transition-fast), border-color var(--transition-fast);
  }

  .upload-zone:hover .type-chip {
    color: var(--text);
    border-color: rgba(245, 166, 35, 0.3);
  }

  /* Progress bar */
  .progress-bar-track {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--border);
    border-radius: 0 0 var(--radius-lg) var(--radius-lg);
    overflow: hidden;
  }

  .progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent-hover));
    border-radius: inherit;
    transition: width 0.2s ease-out;
    box-shadow: 0 0 8px rgba(245, 166, 35, 0.6);
  }

  .progress-label {
    position: absolute;
    bottom: 8px;
    right: var(--space-md);
    font-size: var(--text-xs);
    font-family: var(--font-mono);
    color: var(--accent);
    font-weight: 600;
  }

  /* Spinner */
  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Feedback */
  .feedback-message {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    font-size: var(--text-sm);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    animation: slideInFeedback 0.2s ease-out;
  }

  .feedback-message.error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.25);
    color: var(--error);
  }

  .feedback-message.success {
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.25);
    color: var(--success);
  }

  @keyframes slideInFeedback {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .file-input-hidden {
    position: absolute;
    width: 0;
    height: 0;
    opacity: 0;
    pointer-events: none;
  }
</style>
