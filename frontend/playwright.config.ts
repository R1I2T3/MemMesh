import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  timeout: 30_000,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'cd ../backend && .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000',
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 15_000,
    },
    {
      command: 'npm run dev',
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 15_000,
    },
  ],
});
