import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: process.env.CI ? 2 : 0,
  use: { baseURL: 'http://localhost:5173' },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: '.auth/superadmin.json',
      },
      dependencies: ['setup'],
    },
  ],
  webServer: [
    {
      command: 'npm run dev --prefix frontend',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'uv run --project backend uvicorn backend.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
    }
  ]
});
