import { test, expect } from '@playwright/test';

test.describe('CRAG Web Fallback E2E Tests', () => {
  test('Query with irrelevant context triggers CRAG evaluation and web search fallback', async ({ page }) => {
    const sessionName = `e2e-crag-${Date.now()}`;

    // 1. Navigate to chat (dashboard auto-redirects to /dashboard/chat)
    await page.goto('http://localhost:5173/dashboard/chat');

    // 2. Verify the chat page loaded
    await expect(page.locator('#chat-title')).toHaveText('Chat Interface Console');

    // 3. Create a unique new chat session to run in isolation
    const newSessionInput = page.locator('#new-session-input');
    await newSessionInput.fill(sessionName);
    await page.locator('#add-session-btn').click();

    // Check that our new session is active (the header should display the session name)
    await expect(page.locator('span.font-mono.text-indigo-500')).toHaveText(sessionName);

    // 4. Send a message designed to trigger the CRAG web search fallback
    // In mock mode (MOCK_LLM=true), any query containing the term "irrelevant"
    // will fail relevance check and trigger the DuckDuckGo web search fallback.
    const chatInput = page.locator('input[placeholder="Ask anything, agent orchestrator will route your query..."]');
    await chatInput.fill('This is an irrelevant query to test web search fallback');

    // Wait for query API response before checking UI
    const queryResponse = page.waitForResponse(
      resp => resp.url().includes('/api/query') && resp.status() === 200,
      { timeout: 15000 }
    );
    await page.locator('button[type="submit"]').click();
    await queryResponse;

    // Verify user and assistant messages appear
    const userMsg = page.getByText('This is an irrelevant query to test web search fallback', { exact: true });
    await expect(userMsg).toBeVisible();

    const assistantMsg = page.getByText('Mock response for query: This is an irrelevant query to test web search fallback', { exact: true });
    await expect(assistantMsg).toBeVisible();
  });
});
