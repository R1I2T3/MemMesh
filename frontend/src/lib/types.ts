export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RefreshedTokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  user_id: string;
  email: string;
  global_role: string;
}

export interface ApiError {
  detail: string;
}
