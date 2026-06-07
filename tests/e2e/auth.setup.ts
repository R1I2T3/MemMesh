import { test as setup, expect } from '@playwright/test';
const authFile = '.auth/superadmin.json';

setup('authenticate as superadmin', async ({ page }) => {
  await page.goto('http://localhost:5173/');
  await page.locator('#email-input').fill('superadmin@memmesh.com');
  await page.locator('#password-input').fill('admin_secret_password_change_me');
  await page.locator('#login-button').click();
  await expect(page.locator('#dashboard-header')).toBeVisible({ timeout: 15000 });
  await page.context().storageState({ path: authFile });
});
