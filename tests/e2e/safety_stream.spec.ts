import { test, expect } from '@playwright/test';

test.describe('Safety Validation & SSE Streaming E2E Tests', () => {
  test('User query with toxic content is blocked', async ({ page }) => {
    const sessionName = `e2e-safety-toxic-${Date.now()}`;
    await page.goto('http://localhost:5173/dashboard/chat');
    await expect(page.locator('#chat-title')).toHaveText('Chat Interface Console');

    // Create session
    await page.locator('#new-session-input').fill(sessionName);
    await page.locator('#add-session-btn').click();

    // Enter toxic query
    const chatInput = page.locator('input[placeholder="Ask anything, agent orchestrator will route your query..."]');
    await chatInput.fill('This is a toxic and offensive query.');

    // Wait for the response which should fail with 400
    const queryResponse = page.waitForResponse(
      resp => resp.url().includes('/api/query/stream') && resp.status() === 400,
      { timeout: 15000 }
    );
    await page.locator('button[type="submit"]').click();
    await queryResponse;

    // Verify error is displayed on UI
    await expect(page.locator('text=Query contains toxic language and is blocked.')).toBeVisible();
  });

  test('User query with PII has email scrubbed before persisting', async ({ page }) => {
    const sessionName = `e2e-safety-pii-${Date.now()}`;
    await page.goto('http://localhost:5173/dashboard/chat');

    // Create session
    await page.locator('#new-session-input').fill(sessionName);
    await page.locator('#add-session-btn').click();

    // Enter PII query
    const chatInput = page.locator('input[placeholder="Ask anything, agent orchestrator will route your query..."]');
    await chatInput.fill('My email is test.user@example.com, please contact me.');

    // Wait for successful stream
    const queryResponse = page.waitForResponse(
      resp => resp.url().includes('/api/query/stream') && resp.status() === 200,
      { timeout: 15000 }
    );
    await page.locator('button[type="submit"]').click();
    await queryResponse;

    // Verify that the email is scrubbed to [EMAIL] in the chat feed
    await expect(page.getByText('My email is [EMAIL], please contact me.', { exact: true })).toBeVisible();
  });

  test('User query with client-side SQL injection pattern is blocked locally', async ({ page }) => {
    await page.goto('http://localhost:5173/dashboard/chat');

    const chatInput = page.locator('input[placeholder="Ask anything, agent orchestrator will route your query..."]');
    await chatInput.fill('SELECT * FROM users;');

    await page.locator('button[type="submit"]').click();

    // Verify that the error is displayed on UI immediately without sending request
    await expect(page.locator('text=Input query failed client-side security checks')).toBeVisible();
  });

  test('LLM output with toxic content is blocked', async ({ page }) => {
    const sessionName = `e2e-safety-toxic-out-${Date.now()}`;
    await page.goto('http://localhost:5173/dashboard/chat');

    // Create session
    await page.locator('#new-session-input').fill(sessionName);
    await page.locator('#add-session-btn').click();

    const chatInput = page.locator('input[placeholder="Ask anything, agent orchestrator will route your query..."]');
    await chatInput.fill('trigger unsafe response');

    // Wait for the response which should fail with 400
    const queryResponse = page.waitForResponse(
      resp => resp.url().includes('/api/query/stream') && resp.status() === 400,
      { timeout: 15000 }
    );
    await page.locator('button[type="submit"]').click();
    await queryResponse;

    // Verify error is displayed on UI
    await expect(page.locator('text=Output contains toxic language and is blocked.')).toBeVisible();
  });

  test('LLM output with PII has email scrubbed before persisting and streaming', async ({ page }) => {
    const sessionName = `e2e-safety-pii-out-${Date.now()}`;
    await page.goto('http://localhost:5173/dashboard/chat');

    // Create session
    await page.locator('#new-session-input').fill(sessionName);
    await page.locator('#add-session-btn').click();

    const chatInput = page.locator('input[placeholder="Ask anything, agent orchestrator will route your query..."]');
    await chatInput.fill('trigger output pii');

    // Wait for successful stream
    const queryResponse = page.waitForResponse(
      resp => resp.url().includes('/api/query/stream') && resp.status() === 200,
      { timeout: 15000 }
    );
    await page.locator('button[type="submit"]').click();
    await queryResponse;
    await expect(chatInput).toBeEnabled();

    // Verify that the email is scrubbed to [EMAIL] in the assistant response bubble
    await expect(page.getByText('The email address is [EMAIL].')).toBeVisible();
  });
});
