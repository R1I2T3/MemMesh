import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/login');
  });

  test('should display the login page', async ({ page }) => {
    await expect(page.locator('h1')).toHaveText('MemMesh');
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.locator('#login-submit')).toBeVisible();
  });

  test('should show error on invalid credentials', async ({ page }) => {
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'wrongpassword');
    await page.click('#login-submit');

    await expect(page.locator('[role="alert"]')).toBeVisible();
    await expect(page.locator('[role="alert"]')).toContainText('Invalid email or password');
  });

  test('should login successfully and redirect to dashboard', async ({ page }) => {
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');

    // Should redirect to dashboard
    await page.waitForURL('**/dashboard');
    await expect(page.locator('h1')).toHaveText('Welcome to MemMesh');
    await expect(page.locator('.user-email')).toHaveText('admin@example.com');
    await expect(page.locator('.user-role')).toHaveText('superadmin');
  });

  test('should persist session across page reloads', async ({ page }) => {
    // Login first
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');

    // Reload the page
    await page.reload();

    // Should still be on dashboard
    await expect(page.locator('h1')).toHaveText('Welcome to MemMesh');
    await expect(page.locator('.user-email')).toHaveText('admin@example.com');
  });

  test('should logout and redirect to login', async ({ page }) => {
    // Login first
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');

    // Click logout
    await page.click('#logout-button');

    // Should redirect to login
    await page.waitForURL('**/login');
    await expect(page.locator('h1')).toHaveText('MemMesh');
  });

  test('should redirect unauthenticated users to login', async ({ page }) => {
    // Try to access dashboard directly
    await page.goto('/dashboard');

    // Should redirect to login
    await page.waitForURL('**/login');
    await expect(page.locator('#login-submit')).toBeVisible();
  });

  test('should redirect authenticated users from login to dashboard', async ({ page }) => {
    // Login first
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');

    // Try to go back to login
    await page.goto('/login');

    // Should redirect back to dashboard
    await page.waitForURL('**/dashboard');
  });
});
