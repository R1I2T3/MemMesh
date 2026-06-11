import { test, expect } from '@playwright/test';

test('should switch themes and navigate to chat', async ({ page }) => {
  await page.goto('http://localhost:5173/dashboard');
  const html = page.locator('html');
  const toggle = page.locator('#theme-toggle');
  await expect(html).not.toHaveClass(/dark/);
  await toggle.click();
  await expect(html).toHaveClass(/dark/);

  await page.locator('#link-chat').click();
  await expect(page.locator('#chat-title')).toContainText('Chat Interface');
});
