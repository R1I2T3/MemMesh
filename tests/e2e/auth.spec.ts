import { test, expect } from '@playwright/test';

test('authenticated user sees dashboard', async ({ page }) => {
  await page.goto('http://localhost:5173/dashboard');
  await expect(page.locator('#dashboard-header')).toBeVisible();
});

test('unauthenticated user is redirected to login', async ({ browser }) => {
  const context = await browser.newContext({ storageState: { cookies: [], origins: [] } }); // force unauthenticated
  const page = await context.newPage();
  await page.goto('http://localhost:5173/dashboard');
  await expect(page).toHaveURL(/\/$/);
  await context.close();
});

test('authenticated user visiting landing page is redirected to dashboard', async ({ page }) => {
  await page.goto('http://localhost:5173/');
  await expect(page).toHaveURL(/\/dashboard\/chat$/);
});
