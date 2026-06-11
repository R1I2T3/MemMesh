import { test, expect } from '@playwright/test';

test.use({ storageState: { cookies: [], origins: [] } });

test('health endpoint returns all services', async ({ request }) => {
  const res = await request.get('http://127.0.0.1:8000/api/health');
  expect(res.ok()).toBeTruthy();
  const data = await res.json();
  expect(data.services).toHaveProperty('mysql');
});

test('unauthenticated API calls return 401', async ({ request }) => {
  const res = await request.get('http://127.0.0.1:8000/api/admin/teams');
  expect(res.status()).toBe(401);
});
