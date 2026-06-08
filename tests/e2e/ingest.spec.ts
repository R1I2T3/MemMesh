import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://127.0.0.1:8000';
const SUPERADMIN_EMAIL = process.env.SUPERADMIN_EMAIL || 'superadmin@memmesh.com';
const SUPERADMIN_PASSWORD = process.env.SUPERADMIN_PASSWORD || 'admin_secret_password_change_me';

test.describe('Document Ingestion E2E Tests', () => {
  test('User can select team, upload a document, and view active upload/completed lists', async ({ page, request }) => {
    // 1. Create a team via API first to make sure one exists
    // Get superadmin token
    const loginRes = await request.post(`${BACKEND_URL}/api/auth/login`, {
      data: {
        email: SUPERADMIN_EMAIL,
        password: SUPERADMIN_PASSWORD,
      },
    });
    expect(loginRes.status()).toBe(200);
    const loginData = await loginRes.json();
    const token = loginData.token;

    const uniqueSuffix = Date.now().toString();
    const teamName = `Ingest-E2E-Team-${uniqueSuffix}`;

    const teamRes = await request.post(`${BACKEND_URL}/api/admin/teams`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      data: { name: teamName }
    });
    expect(teamRes.status()).toBe(200);
    const teamData = await teamRes.json();
    const teamId = teamData.team_id;

    try {
      // 2. Go to dashboard and navigate to docs console
      await page.goto('/dashboard');
      const docsLink = page.locator('#link-docs');
      await expect(docsLink).toBeVisible();
      await docsLink.click();

      await expect(page).toHaveURL(/.*\/dashboard\/docs/);
      await expect(page.locator('#docs-title')).toHaveText('Document Ingestion Console');

      // 3. Select the team we created in the dropdown
      const teamSelectTrigger = page.locator('#team-select');
      await expect(teamSelectTrigger).toBeVisible();
      await teamSelectTrigger.click();

      // Select our team item
      const teamOption = page.getByRole('option', { name: teamName });
      await expect(teamOption).toBeVisible();
      await teamOption.click();

      // 4. Test file upload input and button presence
      const fileInput = page.locator('#file-input');
      await expect(fileInput).toBeVisible();

      const uploadBtn = page.locator('#upload-button');
      await expect(uploadBtn).toBeVisible();

      // Select a file to upload
      await fileInput.setInputFiles({
        name: 'e2e_test_doc.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('This is a test document content for MemMesh ingestion verification.')
      });

      // Submit upload
      await uploadBtn.click();

      // Verify Active Ingestions contains the task row
      const uploadRow = page.locator('tr:has-text("e2e_test_doc.txt")');
      await expect(uploadRow).toBeVisible();
    } finally {
      // Clean up team
      const cleanupResponse = await request.delete(`${BACKEND_URL}/api/admin/teams/${teamId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      expect(cleanupResponse.status()).toBe(200);
    }
  });
});
