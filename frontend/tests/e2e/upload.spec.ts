import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

test.describe('Document Upload and Preview Flow', () => {
  const teamId = 'team-e2e-upload';
  const teamName = 'Upload E2E Team';

  test.beforeAll(() => {
    // Seed test team and membership inside SQLite directly
    try {
      // Clean up previous test artifacts
      execSync('sqlite3 ../backend/data/db.sqlite3 "DELETE FROM source_docs"');
      execSync(`sqlite3 ../backend/data/db.sqlite3 "DELETE FROM team_members WHERE team_id = '${teamId}'"`);
      execSync(`sqlite3 ../backend/data/db.sqlite3 "DELETE FROM teams WHERE team_id = '${teamId}'"`);

      // Seed the team
      execSync(`sqlite3 ../backend/data/db.sqlite3 "INSERT INTO teams (team_id, name, description) VALUES ('${teamId}', '${teamName}', 'Upload test description')"`);

      // Get admin user_id
      const adminUserId = execSync('sqlite3 ../backend/data/db.sqlite3 "SELECT user_id FROM users WHERE email = \'admin@example.com\'"').toString().trim();

      // Add admin as lead of the test team
      execSync(`sqlite3 ../backend/data/db.sqlite3 "INSERT INTO team_members (membership_id, user_id, team_id, role) VALUES ('m-admin-upload', '${adminUserId}', '${teamId}', 'lead')"`);
    } catch (e) {
      console.warn('Failed to seed DB for upload tests:', e);
    }
  });

  test.beforeEach(async ({ page }) => {
    // Clear storage and login to fetch fresh token containing new membership
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/login');

    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');

    // Switch team context
    const switcher = page.locator('.team-switcher-trigger');
    await expect(switcher).toBeVisible({ timeout: 5000 });
    await switcher.click();

    await expect(page.locator('.team-dropdown')).toBeVisible();
    const dropdownItem = page.locator('.dropdown-item', { hasText: teamName }).first();
    await expect(dropdownItem).toBeVisible();
    await dropdownItem.click();

    await expect(page.locator('.team-dropdown')).not.toBeVisible();
  });

  test('should drag and drop a mock text file, list it, and preview it', async ({ page }) => {
    // 1. Prepare DataTransfer for mock text file
    const txtFileName = 'mock-doc.txt';
    const txtContent = 'Hello world, this is a mock text file for upload testing.';
    
    const dataTransfer = await page.evaluateHandle(([content, filename]) => {
      const dt = new DataTransfer();
      const file = new File([content], filename, { type: 'text/plain' });
      dt.items.add(file);
      return dt;
    }, [txtContent, txtFileName]);

    // 2. Dispatch drop event on the upload zone
    await page.dispatchEvent('.upload-zone', 'drop', { dataTransfer });

    // 3. Verify success message in toast / feedback area
    const successFeedback = page.locator('.feedback-message.success');
    await expect(successFeedback).toBeVisible({ timeout: 10000 });
    await expect(successFeedback).toContainText(`"${txtFileName}" uploaded successfully!`);

    // 4. Verify document is displayed in the list
    const docItem = page.locator('.doc-item', { hasText: txtFileName });
    await expect(docItem).toBeVisible({ timeout: 10000 });
    await expect(docItem.locator('.doc-type-badge')).toHaveText('TEXT/PLAIN');

    // 5. Click on the document list item to select it
    await docItem.click();

    // 6. Assert preview panel shows details
    const previewPanel = page.locator('.preview-panel');
    await expect(previewPanel.locator('.doc-title')).toHaveText(txtFileName);
    await expect(previewPanel.locator('.filename-value')).toHaveText(txtFileName);
    await expect(previewPanel.locator('.type-chip')).toHaveText('TEXT/PLAIN');

    // 7. Verify text placeholder is shown in the preview area
    const previewArea = previewPanel.locator('.preview-area');
    await expect(previewArea.locator('h4')).toHaveText('Text File');
    await expect(previewArea).toContainText('Raw text content will be displayed here');
  });

  test('should upload an image file using file input, and show image preview placeholder', async ({ page }) => {
    const pngFileName = 'mock-image.png';
    const filePayload = {
      name: pngFileName,
      mimeType: 'image/png',
      buffer: Buffer.from('fake-png-binary-content')
    };

    // 1. Select the file using the hidden file input
    await page.setInputFiles('input[type="file"]', filePayload);

    // 2. Verify success feedback message
    const successFeedback = page.locator('.feedback-message.success');
    await expect(successFeedback).toBeVisible({ timeout: 10000 });
    await expect(successFeedback).toContainText(`"${pngFileName}" uploaded successfully!`);

    // 3. Verify image file is displayed in the list
    const docItem = page.locator('.doc-item', { hasText: pngFileName });
    await expect(docItem).toBeVisible({ timeout: 10000 });
    await expect(docItem.locator('.doc-type-badge')).toHaveText('IMAGE/PNG');

    // 4. Click to open preview
    await docItem.click();

    // 5. Verify image preview details
    const previewPanel = page.locator('.preview-panel');
    await expect(previewPanel.locator('.doc-title')).toHaveText(pngFileName);
    await expect(previewPanel.locator('.filename-value')).toHaveText(pngFileName);
    await expect(previewPanel.locator('.type-chip')).toHaveText('IMAGE/PNG');

    // 6. Verify image placeholder preview
    const previewArea = previewPanel.locator('.preview-area');
    await expect(previewArea.locator('.image-placeholder-name')).toHaveText(pngFileName);
    await expect(previewArea).toContainText('Image preview will be available');
  });

  test('should display error when attempting to upload duplicate file content', async ({ page }) => {
    const txtFileName = 'dup-doc.txt';
    const txtContent = 'Unique content for duplicate testing.';

    // 1. Upload first time
    const dt1 = await page.evaluateHandle(([content, filename]) => {
      const dt = new DataTransfer();
      const file = new File([content], filename, { type: 'text/plain' });
      dt.items.add(file);
      return dt;
    }, [txtContent, txtFileName]);

    await page.dispatchEvent('.upload-zone', 'drop', { dataTransfer: dt1 });

    // Wait for first success
    await expect(page.locator('.feedback-message.success')).toBeVisible({ timeout: 10000 });

    // 2. Upload second time (with a different filename but same content hash)
    const dt2 = await page.evaluateHandle(([content]) => {
      const dt = new DataTransfer();
      const file = new File([content], 'other-name.txt', { type: 'text/plain' });
      dt.items.add(file);
      return dt;
    }, [txtContent]);

    await page.dispatchEvent('.upload-zone', 'drop', { dataTransfer: dt2 });

    // 3. Verify duplicate error message is shown
    const errorFeedback = page.locator('.feedback-message.error');
    await expect(errorFeedback).toBeVisible({ timeout: 10000 });
    await expect(errorFeedback).toContainText('Document with same content already uploaded');
  });
});
