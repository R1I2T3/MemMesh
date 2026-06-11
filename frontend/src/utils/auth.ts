interface TokenPayload { sub: string; email: string; role: string; exp: number; }

export function parseTokenPayload(token: string): TokenPayload | null {
  try {
    if (!token || token.split('.').length !== 3) return null;
    const base64Url = token.split('.')[1];
    const json = atob(base64Url.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch { return null; }
}

export function isTokenExpired(token: string): boolean {
  const payload = parseTokenPayload(token);
  if (!payload?.exp) return true;
  return Date.now() / 1000 > payload.exp;
}

export function getStoredAuth(): { token: string; role: string } | null {
  const token = localStorage.getItem('token');
  if (!token || isTokenExpired(token)) {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    return null;
  }
  return { token, role: localStorage.getItem('role') || 'user' };
}
