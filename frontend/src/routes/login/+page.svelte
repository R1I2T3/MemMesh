<!-- frontend/src/routes/login/+page.svelte -->
<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { setAuth } from '$lib/auth';

  let email = $state('');
  let password = $state('');
  let error = $state('');
  let isSubmitting = $state(false);

  async function handleLogin(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    isSubmitting = true;

    try {
      const tokens = await api.login({ email, password });
      const user = await (async () => {
        // Temporarily set the token to fetch user info
        const response = await fetch('http://127.0.0.1:8081/auth/me', {
          headers: { Authorization: `Bearer ${tokens.access_token}` },
        });
        if (!response.ok) throw new Error('Failed to fetch user info');
        return response.json();
      })();

      setAuth(tokens.access_token, tokens.refresh_token, user);
      goto('/dashboard');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Login failed';
    } finally {
      isSubmitting = false;
    }
  }
</script>

<svelte:head>
  <title>Login — MemMesh</title>
  <meta name="description" content="Sign in to MemMesh — Advanced RAG System with Hybrid Memory" />
</svelte:head>

<main class="login-container">
  <div class="login-card">
    <div class="login-header">
      <div class="logo" aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="18" stroke="var(--accent)" stroke-width="2" />
          <circle cx="20" cy="14" r="4" fill="var(--accent)" />
          <circle cx="12" cy="26" r="4" fill="var(--accent)" opacity="0.7" />
          <circle cx="28" cy="26" r="4" fill="var(--accent)" opacity="0.7" />
          <line x1="20" y1="18" x2="12" y2="22" stroke="var(--accent)" stroke-width="1.5" opacity="0.5" />
          <line x1="20" y1="18" x2="28" y2="22" stroke="var(--accent)" stroke-width="1.5" opacity="0.5" />
          <line x1="12" y1="26" x2="28" y2="26" stroke="var(--accent)" stroke-width="1.5" opacity="0.3" />
        </svg>
      </div>
      <h1>MemMesh</h1>
      <p class="subtitle">Hybrid Memory RAG System</p>
    </div>

    <form onsubmit={handleLogin} class="login-form" aria-label="Login form">
      {#if error}
        <div class="error-banner" role="alert">
          <span class="error-icon" aria-hidden="true">⚠</span>
          {error}
        </div>
      {/if}

      <div class="field">
        <label for="email">Email</label>
        <input
          id="email"
          type="email"
          bind:value={email}
          placeholder="you@example.com"
          required
          autocomplete="email"
          disabled={isSubmitting}
        />
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          placeholder="Enter your password"
          required
          autocomplete="current-password"
          disabled={isSubmitting}
        />
      </div>

      <button type="submit" class="login-button" disabled={isSubmitting} id="login-submit">
        {#if isSubmitting}
          <span class="button-spinner" aria-hidden="true"></span>
          Signing in…
        {:else}
          Sign In
        {/if}
      </button>
    </form>
  </div>
</main>

<style>
  .login-container {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: var(--space-md);
    background: var(--bg);
  }

  .login-card {
    width: 100%;
    max-width: 420px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-2xl);
    box-shadow: var(--shadow-lg);
  }

  .login-header {
    text-align: center;
    margin-bottom: var(--space-xl);
  }

  .logo {
    display: inline-block;
    margin-bottom: var(--space-md);
    animation: fadeIn 0.6s ease;
  }

  .login-header h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  .subtitle {
    font-size: var(--text-sm);
    color: var(--text-muted);
    margin-top: var(--space-xs);
  }

  .login-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-lg);
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
  }

  .error-icon {
    flex-shrink: 0;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .field label {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-muted);
  }

  .field input {
    width: 100%;
    padding: var(--space-sm) var(--space-md);
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: var(--text-base);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    outline: none;
  }

  .field input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(245, 166, 35, 0.15);
  }

  .field input::placeholder {
    color: var(--text-muted);
    opacity: 0.5;
  }

  .field input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .login-button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-sm);
    width: 100%;
    padding: var(--space-sm) var(--space-lg);
    background: var(--accent);
    color: #0f0f11;
    border: none;
    border-radius: var(--radius-md);
    font-family: var(--font-sans);
    font-size: var(--text-base);
    font-weight: 600;
    cursor: pointer;
    transition: background var(--transition-fast), transform var(--transition-fast), box-shadow var(--transition-fast);
  }

  .login-button:hover:not(:disabled) {
    background: var(--accent-hover);
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow);
  }

  .login-button:active:not(:disabled) {
    transform: translateY(0);
  }

  .login-button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .button-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(15, 15, 17, 0.3);
    border-top-color: #0f0f11;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
