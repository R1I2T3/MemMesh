import { get } from 'svelte/store';
import { authStore, logout } from './auth';
import type { LoginRequest, TokenResponse, RefreshedTokenResponse, User } from './types';

const API_BASE = 'http://localhost:8000';

class ApiClient {
  private getToken(): string | null {
    const state = get(authStore);
    return state.accessToken;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Try to refresh the token
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        // Retry the original request with the new token
        headers['Authorization'] = `Bearer ${this.getToken()}`;
        const retryResponse = await fetch(`${API_BASE}${path}`, {
          ...options,
          headers,
        });
        if (!retryResponse.ok) {
          const error = await retryResponse.json().catch(() => ({ detail: 'Request failed' }));
          throw new Error(error.detail || `HTTP ${retryResponse.status}`);
        }
        return retryResponse.json();
      }
      logout();
      throw new Error('Session expired');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  private async tryRefresh(): Promise<boolean> {
    const state = get(authStore);
    if (!state.refreshToken) return false;

    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });

      if (!response.ok) return false;

      const data: RefreshedTokenResponse = await response.json();
      authStore.update((s) => ({ ...s, accessToken: data.access_token }));
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem('auth');
        if (stored) {
          const parsed = JSON.parse(stored);
          parsed.accessToken = data.access_token;
          localStorage.setItem('auth', JSON.stringify(parsed));
        }
      }
      return true;
    } catch {
      return false;
    }
  }

  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }
}

export const api = new ApiClient();
