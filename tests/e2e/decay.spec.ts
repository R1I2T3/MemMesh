import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://127.0.0.1:8000';
const SUPERADMIN_EMAIL = process.env.SUPERADMIN_EMAIL || 'superadmin@memmesh.com';
const SUPERADMIN_PASSWORD = process.env.SUPERADMIN_PASSWORD || 'admin_secret_password_change_me';

test.describe('System Hardening & Optimization UI E2E Tests', () => {
  test('should display premium hardening control card and trigger tasks successfully for superadmin', async ({ page }) => {
    // 1. We are already authenticated as superadmin by default chromium project storageState
    await page.goto('http://localhost:5173/dashboard/docs');
    
    // 2. Verify System Hardening card is visible
    const card = page.locator('#system-hardening-card');
    await expect(card).toBeVisible();

    // 3. Click Trigger Decay and verify Celery task feedback
    const decayBtn = page.locator('#trigger-decay-btn');
    await expect(decayBtn).toBeVisible();
    await decayBtn.click();

    // 4. Wait for task to trigger and display task status
    const decayTaskId = page.locator('#decay-task-id');
    await expect(decayTaskId).toBeVisible();
    const decayStatus = page.locator('#decay-task-status');
    await expect(decayStatus).toBeVisible();
    
    // 5. Click Trigger Drift and verify Celery task feedback
    const driftBtn = page.locator('#trigger-drift-btn');
    await expect(driftBtn).toBeVisible();
    await driftBtn.click();

    // 6. Wait for task to trigger and display task status
    const driftTaskId = page.locator('#drift-task-id');
    await expect(driftTaskId).toBeVisible();
    const driftStatus = page.locator('#drift-task-status');
    await expect(driftStatus).toBeVisible();
  });

  test('should not display premium hardening card for normal user', async ({ browser, request }) => {
    // Generate unique credentials for regular user
    const uniqueSuffix = Date.now().toString();
    const regEmail = `e2e-reg-decay-${uniqueSuffix}@memmesh.com`;
    const regPassword = 'password-reg-123';

    // 1. Log in as superadmin via API to get token
    const loginRes = await request.post(`${BACKEND_URL}/api/auth/login`, {
      data: {
        email: SUPERADMIN_EMAIL,
        password: SUPERADMIN_PASSWORD,
      },
    });
    expect(loginRes.status()).toBe(200);
    const loginData = await loginRes.json();
    const token = loginData.token;

    // Call API to create a regular user
    const response = await request.post(`${BACKEND_URL}/api/admin/users`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      data: {
        email: regEmail,
        password: regPassword,
        global_role: 'user'
      }
    });
    expect(response.status()).toBe(200);
    const userData = await response.json();
    const regUserId = userData.user_id;

    // 2. Open a new unauthenticated context and log in as the regular user
    const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    const page = await context.newPage();
    
    await page.goto('http://localhost:5173/');
    await page.locator('#email-input').fill(regEmail);
    await page.locator('#password-input').fill(regPassword);
    await page.locator('#login-button').click();

    // Expect to reach dashboard
    await expect(page.locator('#dashboard-header')).toBeVisible();

    // 3. Go to /dashboard/docs
    await page.goto('http://localhost:5173/dashboard/docs');
    
    // 4. Verify System Hardening card is NOT visible
    const card = page.locator('#system-hardening-card');
    await expect(card).not.toBeVisible();

    // Cleanup the created user
    const cleanupResponse = await request.delete(`${BACKEND_URL}/api/admin/users/${regUserId}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    expect(cleanupResponse.status()).toBe(200);

    await context.close();
  });
});
