import { test, expect } from '@playwright/test';

test.describe('Query API & Chat Branching UI E2E Tests', () => {
  test('User can open chat, start a session, send messages, branch a chat, and switch branches', async ({ page }) => {
    const sessionName = `e2e-session-${Date.now()}`;

    // 1. Navigate to chat (dashboard auto-redirects to /dashboard/chat)
    await page.goto('http://localhost:5173/dashboard/chat');

    // 2. Verify the chat page loaded
    await expect(page.locator('#chat-title')).toHaveText('Chat Interface Console');

    // 3. Create a unique new chat session to run in isolation
    const newSessionInput = page.locator('#new-session-input');
    await newSessionInput.fill(sessionName);
    // Find the button with PlusIcon right next to the session input
    await page.locator('#add-session-btn').click();

    // Check that our new session is active (the header should display the session name)
    await expect(page.locator('span.font-mono.text-indigo-500')).toHaveText(sessionName);

    // 4. Send the first linear chat message
    const chatInput = page.locator('input[placeholder="Ask anything, agent orchestrator will route your query..."]');
    await chatInput.fill('What is your status?');

    // Wait for query API response before checking UI
    const queryResponse = page.waitForResponse(
      resp => resp.url().includes('/api/query') && resp.status() === 200,
      { timeout: 15000 }
    );
    await page.locator('button[type="submit"]').click();
    await queryResponse;

    // Verify user and assistant messages appear
    const userMsg = page.getByText('What is your status?', { exact: true });
    await expect(userMsg).toBeVisible();

    const assistantMsg = page.getByText('Mock response for query: What is your status?', { exact: true });
    await expect(assistantMsg).toBeVisible();

    // 5. Hover over the assistant response bubble to reveal the Branch button, then click it
    // Wait for the message bubble to be hoverable
    const assistantBubble = page.locator('div.group').last();
    await assistantBubble.hover();

    const branchBtn = assistantBubble.locator('button:has-text("Branch")');
    await expect(branchBtn).toBeVisible();
    await branchBtn.click();

    // Verify branching helper banner is visible
    const branchBanner = page.locator('text=Branching thread from message:');
    await expect(branchBanner).toBeVisible();

    // Send the first branched question
    await chatInput.fill('First branched path query');
    const branch1Response = page.waitForResponse(
      resp => resp.url().includes('/api/query') && resp.status() === 200,
      { timeout: 15000 }
    );
    await page.locator('button[type="submit"]').click();
    await branch1Response;

    // Verify first branch response is visible
    const branch1Msg = page.getByText('First branched path query', { exact: true });
    await expect(branch1Msg).toBeVisible();

    // 6. Branch from the original assistant message again to create a second branch (bifurcation point)
    // Find the original assistant message and hover/click Branch again
    const firstAssistantBubble = page.locator('div.group').nth(1);
    await firstAssistantBubble.hover();
    await firstAssistantBubble.locator('button:has-text("Branch")').click();

    // Verify branch banner is visible
    await expect(branchBanner).toBeVisible();

    // Send the second branched question
    await chatInput.fill('Second branched path query');
    const branch2Response = page.waitForResponse(
      resp => resp.url().includes('/api/query') && resp.status() === 200,
      { timeout: 15000 }
    );
    await page.locator('button[type="submit"]').click();
    await branch2Response;

    // Verify second branch response is visible
    const branch2Msg = page.getByText('Second branched path query', { exact: true });
    await expect(branch2Msg).toBeVisible();

    // 7. Verify the branch switcher is rendered under the bifurcation point (the first assistant message)
    // Since there are 2 child threads starting from it, a branch switcher "Branch: 2 of 2" (or "1 of 2") should appear
    const switcher = page.locator('text=Branch:');
    await expect(switcher).toBeVisible();

    // Click left arrow on switcher to switch to Branch 1
    const prevBranchBtn = page.locator('button:has(svg.lucide-chevron-left)').first();
    await prevBranchBtn.click();

    // Verify that the first branched path query message is visible, and second branched path query message is hidden
    await expect(page.getByText('First branched path query', { exact: true })).toBeVisible();
    await expect(page.getByText('Second branched path query', { exact: true })).not.toBeVisible();

    // Click right arrow on switcher to switch back to Branch 2
    const nextBranchBtn = page.locator('button:has(svg.lucide-chevron-right)').first();
    await nextBranchBtn.click();

    // Verify that second branched path query is visible, and first is hidden
    await expect(page.getByText('Second branched path query', { exact: true })).toBeVisible();
    await expect(page.getByText('First branched path query', { exact: true })).not.toBeVisible();
  });
});
