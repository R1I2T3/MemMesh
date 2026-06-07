import { test as setup, expect } from '@playwright/test';
const authFile = '.auth/superadmin.json';

setup('authenticate as superadmin', async ({ page }) => {
  const email = process.env.SUPERADMIN_EMAIL || 'superadmin@memmesh.com';
  const password = process.env.SUPERADMIN_PASSWORD || 'admin_secret_password_change_me';

  await page.goto('http://localhost:5173/');
  await page.locator('#email-input').fill(email);
  await page.locator('#password-input').fill(password);
  await page.locator('#login-button').click();
  await expect(page.locator('#dashboard-header')).toBeVisible({ timeout: 15000 });
  await page.context().storageState({ path: authFile });
});
