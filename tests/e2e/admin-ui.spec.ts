import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://127.0.0.1:8000';
const SUPERADMIN_EMAIL = process.env.SUPERADMIN_EMAIL || 'superadmin@memmesh.com';
const SUPERADMIN_PASSWORD = process.env.SUPERADMIN_PASSWORD || 'admin_secret_password_change_me';

test.describe('Admin UI E2E Tests', () => {
  // Setup dialog handler to auto-accept confirmation boxes
  test.beforeEach(async ({ page }) => {
    page.on('dialog', async (dialog) => {
      await dialog.accept();
    });
  });

  test('Superadmin can access admin panel, create/delete teams, users, and manage members', async ({ page, browser }) => {
    // Generate unique names to prevent conflict
    const uniqueSuffix = Date.now().toString();
    const teamName = `E2E-Team-${uniqueSuffix}`;
    const userEmail = `e2e-user-${uniqueSuffix}@memmesh.com`;
    const userPassword = `password-123-${uniqueSuffix}`;

    // 1. Go to dashboard and check admin link
    await page.goto('http://localhost:5173/dashboard');
    const adminLink = page.locator('#link-admin');
    await expect(adminLink).toBeVisible();

    // 2. Navigate to admin panel
    await adminLink.click();
    await expect(page).toHaveURL(/.*\/dashboard\/admin/);
    await expect(page.locator('#admin-title')).toHaveText('Admin Panel');

    // 3. Create a team
    await page.locator('#team-name-input').fill(teamName);
    await page.locator('#team-create-submit').click();

    // Verify team is listed
    const teamRow = page.locator(`tr:has-text("${teamName}")`);
    await expect(teamRow).toBeVisible();

    // 4. Create a user (needed for member management)
    await page.locator('#tab-users').click();
    await page.locator('#user-email-input').fill(userEmail);
    await page.locator('#user-password-input').fill(userPassword);
    await page.locator('#user-role-select').selectOption('user');
    await page.locator('#user-create-submit').click();

    // Verify user is listed
    const userRow = page.locator(`tr:has-text("${userEmail}")`);
    await expect(userRow).toBeVisible();

    // 5. Manage Team Members
    await page.locator('#tab-teams').click();
    
    // Select the team's members view
    const selectMembersBtn = page.locator(`[data-testid="select-team-${teamName}"]`);
    await selectMembersBtn.click();

    // Select user in members dropdown and add
    const userSelect = page.locator('#member-user-select');
    // Wait for the dropdown options to contain the user we created
    await expect(userSelect.locator(`option:has-text("${userEmail}")`)).toBeAttached();
    
    // Select option by label/text or value
    // Since we know the email, we can select the option that has the text
    const optionValue = await userSelect.locator(`option:has-text("${userEmail}")`).getAttribute('value');
    if (!optionValue) {
      throw new Error(`Could not find option with text ${userEmail}`);
    }
    await userSelect.selectOption(optionValue);
    await page.locator('#member-role-select').selectOption('admin');
    await page.locator('#member-add-submit').click();

    // Verify member is listed in members list
    const memberRow = page.locator(`tr:has-text("${userEmail}")`);
    await expect(memberRow).toBeVisible();

    // Remove member
    const removeMemberBtn = memberRow.locator('button:has(.lucide-user-minus)');
    await removeMemberBtn.click();
    await expect(memberRow).not.toBeVisible();

    // 6. Delete team
    const deleteTeamBtn = page.locator(`[data-testid="delete-team-${teamName}"]`);
    await deleteTeamBtn.click();
    await expect(teamRow).not.toBeVisible();

    // 7. Delete user
    await page.locator('#tab-users').click();
    const deleteUserBtn = page.locator(`[data-testid="delete-user-${userEmail}"]`);
    await deleteUserBtn.click();
    await expect(userRow).not.toBeVisible();
  });

  test('Regular user cannot see Admin Panel link and is redirected if visiting direct URL', async ({ browser, request }) => {
    // Generate standard user credentials using API or UI
    const uniqueSuffix = Date.now().toString();
    const regEmail = `e2e-reg-${uniqueSuffix}@memmesh.com`;
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

    // 3. Verify Admin Panel link is NOT visible in the sidebar
    await expect(page.locator('#link-admin')).not.toBeVisible();

    // 4. Try navigating directly to admin URL and expect redirect back to dashboard
    await page.goto('http://localhost:5173/dashboard/admin');
    await expect(page).toHaveURL(/.*\/dashboard/);
    await expect(page).not.toHaveURL(/.*\/dashboard\/admin/);

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
