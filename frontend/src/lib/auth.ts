import { writable } from 'svelte/store';
import type { User } from './types';

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const initialState: AuthState = {
  accessToken: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false,
  isLoading: true,
};

export const authStore = writable<AuthState>(initialState);

/**
 * Initialize auth state from localStorage (called on app start).
 */
export function initAuth(): void {
  if (typeof localStorage === 'undefined') {
    authStore.set({ ...initialState, isLoading: false });
    return;
  }

  const stored = localStorage.getItem('auth');
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      authStore.set({
        accessToken: parsed.accessToken || null,
        refreshToken: parsed.refreshToken || null,
        user: parsed.user || null,
        isAuthenticated: !!parsed.accessToken,
        isLoading: false,
      });
    } catch {
      localStorage.removeItem('auth');
      authStore.set({ ...initialState, isLoading: false });
    }
  } else {
    authStore.set({ ...initialState, isLoading: false });
  }
}

/**
 * Set auth state after successful login.
 */
export function setAuth(accessToken: string, refreshToken: string, user: User): void {
  const state: AuthState = {
    accessToken,
    refreshToken,
    user,
    isAuthenticated: true,
    isLoading: false,
  };
  authStore.set(state);

  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('auth', JSON.stringify({
      accessToken,
      refreshToken,
      user,
    }));
  }
}

/**
 * Clear auth state (logout).
 */
export function logout(): void {
  authStore.set({ ...initialState, isLoading: false });
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('auth');
  }
}
