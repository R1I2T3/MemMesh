import { test, expect } from '@playwright/test';

test.use({ storageState: { cookies: [], origins: [] } });

test('should display all service statuses on login page', async ({ page }) => {
  await page.goto('http://localhost:5173/');
  const statusEl = page.locator('#system-status');
  await expect(statusEl).toBeVisible({ timeout: 10000 });
  await expect(statusEl).toContainText('operational');
});
