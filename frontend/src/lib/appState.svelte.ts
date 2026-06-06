// frontend/src/lib/appState.svelte.ts
import { authStore } from './auth';
import { get } from 'svelte/store';

// Helper to decode JWT and get its payload
export function decodeJwt(token: string): any {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

class AppState {
  theme = $state<'dark' | 'light'>('dark');
  activeTeamId = $state<string | null>(null);

  // Initialize theme from storage/system
  initTheme() {
    if (typeof window === 'undefined') return;
    const stored = localStorage.getItem('theme');
    if (stored === 'dark' || stored === 'light') {
      this.theme = stored;
    } else {
      const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      this.theme = isDark ? 'dark' : 'light';
    }
    this.applyTheme();
  }

  toggleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    this.applyTheme();
  }

  private applyTheme() {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', this.theme);
      localStorage.setItem('theme', this.theme);
    }
  }

  // Get memberships decoded from active JWT
  get memberships(): Array<{ team_id: string; name: string; role: 'user' | 'lead' }> {
    const auth = get(authStore);
    if (!auth.accessToken) return [];
    const decoded = decodeJwt(auth.accessToken);
    return decoded?.team_memberships || [];
  }

  // Active team detail
  get activeTeam() {
    const list = this.memberships;
    if (list.length === 0) return null;
    
    // Auto-select first team if no active selection or if selected team is no longer in memberships
    const found = list.find((m) => m.team_id === this.activeTeamId);
    if (found) return found;

    // Default to the first team
    if (!this.activeTeamId && list[0]) {
      this.activeTeamId = list[0].team_id;
    }
    return list.find((m) => m.team_id === this.activeTeamId) || list[0] || null;
  }
}

export const appState = new AppState();
