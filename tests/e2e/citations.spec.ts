import { test, expect } from '@playwright/test';

test.describe('Citation Data Flow & PDF Viewer Drawer E2E Tests', () => {
  test('Clicking inline citation opens drawer with PDF visualization details', async ({ page }) => {
    // Add console and page error logging to diagnose issues
    page.on('console', msg => console.log(`BROWSER LOG [${msg.type()}]:`, msg.text()));
    page.on('pageerror', err => console.log('BROWSER EXCEPTION:', err.message));

    const sessionName = `e2e-citations-${Date.now()}`;

    // 1. Navigate to chat page
    await page.goto('http://localhost:5173/dashboard/chat');

    // 2. Verify title
    await expect(page.locator('#chat-title')).toHaveText('Chat Interface');

    // 3. Create a unique new session
    const newSessionInput = page.locator('#new-session-input');
    await newSessionInput.fill(sessionName);
    await page.locator('#add-session-btn').click();

    // Check that session is active
    await expect(page.locator('#chat-title + p span')).toHaveText(sessionName);

    const mockCitations = [
      {
        id: 1,
        type: 'pdf',
        content: 'This is a mock excerpt from page 5 of the contract agreement.',
        source: 'contract_agreement_2026.pdf',
        page: 5,
        bbox: [0.1, 0.15, 0.45, 0.35],
      },
      {
        id: 2,
        type: 'web',
        content: 'Web source excerpt describing safety guidelines.',
        source: 'Safety Wikipedia',
        url: 'https://en.wikipedia.org/wiki/Safety',
      }
    ];

    // Mock the messages history endpoint to return both the user and assistant messages
    const mockUserMessage = {
      message_id: 'user-msg-999',
      session_id: sessionName,
      parent_message_id: null,
      role: 'user',
      content: 'Give me citation details',
      created_at: new Date().toISOString(),
    };
    const mockAssistantMessage = {
      message_id: 'assistant-msg-999',
      session_id: sessionName,
      parent_message_id: 'user-msg-999',
      role: 'assistant',
      content: 'Based on the contract [1] and wikipedia [2], please stay safe.',
      citations: mockCitations,
      created_at: new Date().toISOString(),
    };

    await page.route('**/api/chat/messages*', async (route) => {
      console.log(`PLAYWRIGHT ROUTE INTERCEPTED: ${route.request().method()} ${route.request().url()}`);
      await route.fulfill({
        status: 200,
        headers: {
          'Access-Control-Allow-Origin': 'http://localhost:5173',
          'Access-Control-Allow-Credentials': 'true',
          'Content-Type': 'application/json',
        },
        json: {
          messages: [mockUserMessage, mockAssistantMessage]
        }
      });
    });

    // 4. Intercept the SSE stream query API and mock citation data with proper CORS/OPTIONS handling
    await page.route('**/api/query/stream*', async (route) => {
      const method = route.request().method();
      console.log(`PLAYWRIGHT ROUTE INTERCEPTED: ${method} ${route.request().url()}`);
      
      // Handle CORS preflight request
      if (method === 'OPTIONS') {
        await route.fulfill({
          status: 200,
          headers: {
            'Access-Control-Allow-Origin': 'http://localhost:5173',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Authorization, X-Active-Team-ID, Content-Type',
            'Access-Control-Allow-Credentials': 'true',
          },
        });
        return;
      }

      // Respond with SSE data chunks and CORS headers
      const headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': 'http://localhost:5173',
        'Access-Control-Allow-Credentials': 'true',
      };

      await route.fulfill({
        status: 200,
        headers,
        body: [
          `data: ${JSON.stringify({ type: 'session', session_id: sessionName, user_message_id: 'user-msg-999', message_id: 'assistant-msg-999' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'Based ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'on ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'the ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'contract ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: '[1] ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'and ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'wikipedia ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: '[2], ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'please ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'stay ' })}\n\n`,
          `data: ${JSON.stringify({ type: 'text_chunk', content: 'safe.' })}\n\n`,
          `data: ${JSON.stringify({ type: 'citation', id: 1, source: 'contract_agreement_2026.pdf', content: 'This is a mock excerpt from page 5 of the contract agreement.', page: 5, bbox: [0.1, 0.15, 0.45, 0.35] })}\n\n`,
          `data: ${JSON.stringify({ type: 'citation', id: 2, source: 'Safety Wikipedia', url: 'https://en.wikipedia.org/wiki/Safety', content: 'Web source excerpt describing safety guidelines.' })}\n\n`,
          'data: {"type": "done"}\n\n',
        ].join(''),
      });
    });

    // 5. Send message
    const chatInput = page.locator('input[placeholder="Ask anything, agent orchestrator will route your query..."]');
    await chatInput.fill('Give me citation details');
    await page.locator('button[type="submit"]').click();

    // Verify user message appears in chat feed
    await expect(page.getByText('Give me citation details')).toBeVisible();

    // Verify the response content renders with the inline citation buttons
    const responseContainer = page.locator('div.group').last();
    
    // Check that citation buttons are rendered
    const citationBtn1 = responseContainer.locator('button:has-text("[1]")');
    const citationBtn2 = responseContainer.locator('button:has-text("[2]")');
    
    await expect(citationBtn1).toBeVisible({ timeout: 10000 });
    await expect(citationBtn2).toBeVisible({ timeout: 10000 });

    // 6. Click the first citation button [1] to open the drawer
    await citationBtn1.click();

    // Verify the sheet/drawer is visible and contains expected contents
    const drawerTitle = page.locator('[data-slot="sheet-title"]');
    await expect(drawerTitle).toBeVisible();
    await expect(drawerTitle).toHaveText('contract_agreement_2026.pdf');
    await expect(page.getByText('Page 5', { exact: true })).toBeVisible();
    await expect(page.getByText('This is a mock excerpt from page 5 of the contract agreement.')).toBeVisible();
    await expect(page.getByText('Document View')).toBeVisible();
    await expect(page.getByText('bbox: [0.10, 0.15, 0.45, 0.35]')).toBeVisible();

    // Close the drawer to release the page overlay lock
    const closeBtn = page.locator('[data-slot="sheet-close"]');
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();
    await expect(drawerTitle).not.toBeVisible();

    // 7. Click the second citation button [2] to view the web details
    await citationBtn2.click();
    await expect(drawerTitle).toBeVisible();
    await expect(drawerTitle).toHaveText('Safety Wikipedia');
    await expect(page.getByText('Web Search')).toBeVisible();
    await expect(page.getByText('Web source excerpt describing safety guidelines.', { exact: true })).toBeVisible();
    await expect(page.getByText('Webpage View (Simulated)')).toBeVisible();
    await expect(page.locator('a[href="https://en.wikipedia.org/wiki/Safety"]')).toBeVisible();
  });
});
