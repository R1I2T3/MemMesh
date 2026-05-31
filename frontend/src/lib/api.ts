import { get } from 'svelte/store';
import { authStore, logout } from './auth';
import type { LoginRequest, TokenResponse, RefreshedTokenResponse, User, Team, TeamMember, UserListItem } from './types';

const API_BASE = 'http://127.0.0.1:8081';

class ApiClient {
  private refreshPromise: Promise<boolean> | null = null;

  private getToken(): string | null {
    const state = get(authStore);
    return state.accessToken;
  }

  private async safeJson<T>(response: Response, fallbackDetail = 'Request failed'): Promise<T> {
    try {
      const text = await response.text();
      return text ? JSON.parse(text) : {} as T;
    } catch {
      return { detail: fallbackDetail } as unknown as T;
    }
  }

  private getNormalizedHeaders(customHeaders: RequestInit['headers']): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (!customHeaders) return headers;

    if (customHeaders instanceof Headers) {
      customHeaders.forEach((value, key) => {
        headers[key] = value;
      });
    } else if (Array.isArray(customHeaders)) {
      customHeaders.forEach(([key, value]) => {
        headers[key] = value;
      });
    } else {
      Object.assign(headers, customHeaders);
    }

    return headers;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers = this.getNormalizedHeaders(options.headers);

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
          const error = await this.safeJson<{ detail?: string }>(retryResponse);
          throw new Error(error.detail || `HTTP ${retryResponse.status}`);
        }
        return this.safeJson<T>(retryResponse);
      }
      logout();
      throw new Error('Session expired');
    }

    if (!response.ok) {
      const error = await this.safeJson<{ detail?: string }>(response);
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return this.safeJson<T>(response);
  }

  private async tryRefresh(): Promise<boolean> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    const state = get(authStore);
    if (!state.refreshToken) return false;

    this.refreshPromise = (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: state.refreshToken }),
        });

        if (!response.ok) return false;

        const data = await this.safeJson<RefreshedTokenResponse>(response);
        authStore.update((s) => ({ ...s, accessToken: data.access_token }));
        if (typeof localStorage !== 'undefined') {
          try {
            const stored = localStorage.getItem('auth');
            if (stored) {
              const parsed = JSON.parse(stored);
              parsed.accessToken = data.access_token;
              localStorage.setItem('auth', JSON.stringify(parsed));
            }
          } catch {
            // Ignore Storage quota/permission issues
          }
        }
        return true;
      } catch {
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await this.safeJson<{ detail?: string }>(response, 'Login failed');
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return this.safeJson<TokenResponse>(response);
  }

  async getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  async listTeams(): Promise<Team[]> {
    return this.request<Team[]>('/admin/teams');
  }

  async createTeam(data: { name: string; description: string | null }): Promise<Team> {
    return this.request<Team>('/admin/teams', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteTeam(teamId: string): Promise<void> {
    return this.request<void>(`/admin/teams/${teamId}`, {
      method: 'DELETE',
    });
  }

  async listTeamMembers(teamId: string): Promise<TeamMember[]> {
    return this.request<TeamMember[]>(`/admin/teams/${teamId}/members`);
  }

  async addTeamMember(teamId: string, data: { user_id: string; role: 'user' | 'lead' }): Promise<TeamMember> {
    return this.request<TeamMember>(`/admin/teams/${teamId}/members`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async removeTeamMember(teamId: string, userId: string): Promise<void> {
    return this.request<void>(`/admin/teams/${teamId}/members/${userId}`, {
      method: 'DELETE',
    });
  }

  async listUsers(): Promise<UserListItem[]> {
    return this.request<UserListItem[]>('/admin/users');
  }
}

export const api = new ApiClient();
