<!-- frontend/src/routes/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { authStore } from '$lib/auth';

  onMount(() => {
    const unsubscribe = authStore.subscribe((state) => {
      if (!state.isLoading) {
        if (state.isAuthenticated) {
          goto('/dashboard');
        } else {
          goto('/login');
        }
        unsubscribe();
      }
    });
  });
</script>

<div class="loading-screen" role="status" aria-label="Redirecting...">
  <div class="loading-spinner"></div>
</div>

<style>
  .loading-screen {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background-color: var(--bg);
  }

  .loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
