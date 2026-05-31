import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

test.describe('Teams and User Roles E2E Flow', () => {
  test.beforeAll(() => {
    // Seed some test users and clear previous test data inside SQLite directly
    try {
      execSync('sqlite3 ../backend/data/db.sqlite3 "DELETE FROM team_members"');
      execSync('sqlite3 ../backend/data/db.sqlite3 "DELETE FROM teams"');
      execSync('sqlite3 ../backend/data/db.sqlite3 "DELETE FROM users WHERE email IN (\'e2e-member@test.com\', \'e2e-lead@test.com\')"');
      
      execSync('sqlite3 ../backend/data/db.sqlite3 "INSERT OR IGNORE INTO users (user_id, email, password_hash, global_role) VALUES (\'user-e2e-member\', \'e2e-member@test.com\', \'fake-hash\', \'user\')"');
      execSync('sqlite3 ../backend/data/db.sqlite3 "INSERT OR IGNORE INTO users (user_id, email, password_hash, global_role) VALUES (\'user-e2e-lead\', \'e2e-lead@test.com\', \'fake-hash\', \'user\')"');
    } catch (e) {
      console.warn('Failed to seed E2E users via SQLite, proceeding anyway...', e);
    }
  });

  test.beforeEach(async ({ page }) => {
    // Login as Admin before each test
    await page.goto('/login');
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');
  });

  test('should display the Teams and Users admin navigation links', async ({ page }) => {
    const teamsLink = page.locator('a[href="/admin/teams"]');
    const usersLink = page.locator('a[href="/admin/users"]');
    await expect(teamsLink).toBeVisible();
    await expect(usersLink).toBeVisible();
  });

  test('should allow creating, viewing, and managing a team', async ({ page }) => {
    // 1. Go to Teams panel
    await page.click('a[href="/admin/teams"]');
    await page.waitForURL('**/admin/teams');

    // 2. Click Create Team via explicit ID trigger
    const createBtn = page.locator('#create-team-trigger');
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    // 3. Fill and submit modal form
    await page.waitForSelector('#teamName');
    await page.fill('#teamName', 'Engineering Team');
    await page.fill('#teamDesc', 'Our primary engineering workspace');
    await page.click('#create-team-submit');

    // 4. Assert team card is displayed in listing
    const teamCard = page.locator('.team-card', { hasText: 'Engineering Team' });
    await expect(teamCard).toBeVisible({ timeout: 10000 });
    await expect(teamCard.locator('.team-desc')).toHaveText('Our primary engineering workspace');

    // 5. Open Manage Members Drawer
    await teamCard.locator('button:has-text("Manage Members")').click();
    await page.waitForSelector('.drawer-content');
    await expect(page.locator('#drawer-title')).toContainText('Engineering Team');

    // 6. Select a user to add to the team
    await page.selectOption('#user-to-add-select', 'user-e2e-member');
    await page.selectOption('#role-to-add-select', 'user');
    await page.click('#add-member-submit');

    // 7. Verify member is listed in drawer
    const memberRow = page.locator('.member-item', { hasText: 'e2e-member@test.com' });
    await expect(memberRow).toBeVisible({ timeout: 5000 });
    await expect(memberRow.locator('.member-role-badge')).toContainText('Member');

    // 8. Close drawer
    await page.click('.close-drawer');
    await expect(page.locator('.drawer-content')).not.toBeVisible();
  });

  test('should support selecting active team context', async ({ page }) => {
    // 1. Create a team dynamically first if none exist
    try {
      execSync('sqlite3 ../backend/data/db.sqlite3 "INSERT OR IGNORE INTO teams (team_id, name, description) VALUES (\'team-e2e-active\', \'Active Test Team\', \'Test team\')"');
    } catch (e) {
      console.warn('Failed to seed teams', e);
    }

    // 2. Add admin to team using their real user_id dynamically
    try {
      const adminUserId = execSync('sqlite3 ../backend/data/db.sqlite3 "SELECT user_id FROM users WHERE email = \'admin@example.com\'"').toString().trim();
      execSync(`sqlite3 ../backend/data/db.sqlite3 "INSERT OR IGNORE INTO team_members (membership_id, user_id, team_id, role) VALUES ('m-admin-e2e', '${adminUserId}', 'team-e2e-active', 'lead')"`);
    } catch (e) {
      console.warn('Failed to seed admin membership via SQLite', e);
    }

    // 3. Clear storage and re-login to acquire updated JWT carrying the membership
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/login');
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');

    // 4. Active switcher should now be visible and click to open dropdown
    const switcher = page.locator('.team-switcher-trigger');
    await expect(switcher).toBeVisible({ timeout: 5000 });
    await switcher.click();

    // 5. Dropdown options should display
    await expect(page.locator('.team-dropdown')).toBeVisible();
    
    // 6. Select the team
    const dropdownItem = page.locator('.dropdown-item', { hasText: 'Active Test Team' }).first();
    await expect(dropdownItem).toBeVisible();
    await dropdownItem.click();

    // 7. Switching context should close dropdown
    await expect(page.locator('.team-dropdown')).not.toBeVisible();
  });
});
