import { test, expect } from '@playwright/test';

test.describe('RLHF Feedback Loop & DeepEval Metrics E2E Tests', () => {
  test('Superadmin can submit thumbs up/down feedback on chat page', async ({ page }) => {
    // Enable logging for diagnostics
    page.on('console', msg => console.log(`BROWSER LOG [${msg.type()}]:`, msg.text()));
    page.on('pageerror', err => console.log('BROWSER EXCEPTION:', err.message));

    // Mock chat messages to show an assistant response
    await page.route('**/api/chat/messages*', async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          'Access-Control-Allow-Origin': 'http://localhost:5173',
          'Access-Control-Allow-Credentials': 'true',
          'Content-Type': 'application/json',
        },
        json: {
          messages: [
            {
              message_id: 'user-msg-e2e',
              session_id: 'default-session',
              parent_message_id: null,
              role: 'user',
              content: 'What is MemMesh?',
              created_at: new Date().toISOString(),
            },
            {
              message_id: 'assistant-msg-e2e',
              session_id: 'default-session',
              parent_message_id: 'user-msg-e2e',
              role: 'assistant',
              content: 'MemMesh is a memory RAG system.',
              created_at: new Date().toISOString(),
            }
          ]
        }
      });
    });

    // Capture and mock feedback submission API
    let lastSubmittedRating = 0;
    let feedbackSubmissionsCount = 0;

    await page.route('**/api/feedback', async (route) => {
      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON();
        lastSubmittedRating = body.rating;
        feedbackSubmissionsCount++;
        await route.fulfill({
          status: 200,
          headers: {
            'Access-Control-Allow-Origin': 'http://localhost:5173',
            'Access-Control-Allow-Credentials': 'true',
            'Content-Type': 'application/json',
          },
          json: { status: 'submitted', feedback_id: 'fb-e2e-123' }
        });
      } else {
        await route.continue();
      }
    });

    // Navigate to chat
    await page.goto('http://localhost:5173/dashboard/chat');
    await expect(page.locator('#chat-title')).toHaveText('Chat Interface Console');

    // Find thumbs buttons on the assistant message
    const thumbsUpBtn = page.locator('button[title="Thumbs Up"]');
    const thumbsDownBtn = page.locator('button[title="Thumbs Down"]');

    await expect(thumbsUpBtn).toBeVisible();
    await expect(thumbsDownBtn).toBeVisible();

    // Click thumbs up
    await thumbsUpBtn.click();
    expect(feedbackSubmissionsCount).toBe(1);
    expect(lastSubmittedRating).toBe(1);

    // Verify visual feedback (should have text-green class)
    await expect(thumbsUpBtn).toHaveClass(/text-green/);

    // Click thumbs down
    await thumbsDownBtn.click();
    expect(feedbackSubmissionsCount).toBe(2);
    expect(lastSubmittedRating).toBe(-1);

    // Verify visual feedback (should have text-red class)
    await expect(thumbsDownBtn).toHaveClass(/text-red/);
  });

  test('Superadmin docs console displays and runs DeepEval metrics successfully', async ({ page }) => {
    // Mock DeepEval metrics runner endpoint
    await page.route('**/api/eval', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          headers: {
            'Access-Control-Allow-Origin': 'http://localhost:5173',
            'Access-Control-Allow-Credentials': 'true',
            'Content-Type': 'application/json',
          },
          json: [
            {
              feedback_id: 'fb-eval-e2e-id',
              query: 'What is MemMesh?',
              response: 'MemMesh is a memory RAG system.',
              rating: 1,
              faithfulness_score: 0.85,
              relevancy_score: 0.90,
              reason: 'High faithfulness & relevance context.'
            }
          ]
        });
      } else {
        await route.continue();
      }
    });

    // Navigate to docs
    await page.goto('http://localhost:5173/dashboard/docs');
    await expect(page.locator('#docs-title')).toHaveText('Document Ingestion Console');

    // Run DeepEval Metrics button should be visible for superadmin
    const runEvalBtn = page.locator('#run-eval-btn');
    await expect(runEvalBtn).toBeVisible();

    // Click button
    await runEvalBtn.click();

    // Wait for the results table to appear
    const resultsTable = page.locator('#eval-results-table');
    await expect(resultsTable).toBeVisible();

    // Verify results content
    await expect(resultsTable).toContainText('What is MemMesh?');
    await expect(resultsTable).toContainText('MemMesh is a memory RAG system.');
    await expect(resultsTable).toContainText('+1');
    await expect(resultsTable).toContainText('85%');
    await expect(resultsTable).toContainText('90%');
    await expect(resultsTable).toContainText('High faithfulness & relevance context.');
  });
});
