import { expect, test } from 'vitest';
import { parseTokenPayload, isTokenExpired } from './auth';

test('decodes JWT payload correctly', () => {
  // {"sub":"123","role":"superadmin","exp":9999999999}
  const mock = 'h.eyJzdWIiOiIxMjMiLCJyb2xlIjoic3VwZXJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.s';
  const payload = parseTokenPayload(mock);
  expect(payload?.role).toBe('superadmin');
  expect(payload?.sub).toBe('123');
});

test('returns null for invalid tokens', () => {
  expect(parseTokenPayload('not-a-jwt')).toBeNull();
  expect(parseTokenPayload('')).toBeNull();
});

test('detects expired tokens', () => {
  const expired = 'h.eyJzdWIiOiIxIiwiZXhwIjoxfQ.s';
  expect(isTokenExpired(expired)).toBe(true);
});
