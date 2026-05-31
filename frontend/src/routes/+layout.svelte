<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { authStore, initAuth } from '$lib/auth';
  import favicon from '$lib/assets/favicon.svg';
  import '../app.css';

  let { children } = $props();

  const publicPaths = ['/login'];

  onMount(() => {
    initAuth();
  });

  $effect(() => {
    const state = $authStore;
    const currentPath = $page.url.pathname as string;

    if (!state.isLoading && currentPath) {
      // Normalize path to ignore trailing slashes (except for the root path)
      const cleanPath = currentPath.endsWith('/') && currentPath !== '/' 
        ? currentPath.slice(0, -1) 
        : currentPath;

      const isPublic = publicPaths.includes(cleanPath);

      if (!state.isAuthenticated && !isPublic) {
        if (currentPath !== '/login') {
          goto('/login');
        }
      } else if (state.isAuthenticated) {
        if (cleanPath === '/login' || cleanPath === '/') {
          if (currentPath !== '/dashboard') {
            goto('/dashboard');
          }
        }
      }
    }
  });
</script>

<svelte:head>
  <link rel="icon" href={favicon} />
</svelte:head>

{#if $authStore.isLoading}
  <div class="loading-screen" role="status" aria-label="Loading application">
    <div class="loading-spinner"></div>
  </div>
{:else}
  {@render children()}
{/if}

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
