import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://127.0.0.1:8000';
const SUPERADMIN_EMAIL = process.env.SUPERADMIN_EMAIL || 'superadmin@memmesh.com';
const SUPERADMIN_PASSWORD = process.env.SUPERADMIN_PASSWORD || 'admin_secret_password_change_me';

test.describe('Admin CRUD API tests', () => {
  let superadminToken: string;
  let userToken: string;
  let createdUserId: string;
  let createdTeamId: string;

  // Generate unique team names and email addresses to avoid database pollution and conflicts
  const uniqueSuffix = Date.now().toString();
  const testEmail = `e2e-test-user-${uniqueSuffix}@memmesh.com`;
  const testTeamName = `E2ETestTeam-${uniqueSuffix}`;

  test.beforeAll(async ({ request }) => {
    // 1. Log in as superadmin
    const loginRes = await request.post(`${BACKEND_URL}/api/auth/login`, {
      data: {
        email: SUPERADMIN_EMAIL,
        password: SUPERADMIN_PASSWORD,
      },
    });
    expect(loginRes.status()).toBe(200);
    const loginData = await loginRes.json();
    superadminToken = loginData.token;
    expect(superadminToken).toBeDefined();

    // 2. Create a standard user via admin API
    const createUserRes = await request.post(`${BACKEND_URL}/api/admin/users`, {
      headers: {
        Authorization: `Bearer ${superadminToken}`,
      },
      data: {
        email: testEmail,
        password: 'e2e-password-123',
        global_role: 'user',
      },
    });
    expect(createUserRes.status()).toBe(200);
    const createUserData = await createUserRes.json();
    createdUserId = createUserData.user_id;
    expect(createdUserId).toBeDefined();

    // 3. Log in as the newly created user to get their token
    const userLoginRes = await request.post(`${BACKEND_URL}/api/auth/login`, {
      data: {
        email: testEmail,
        password: 'e2e-password-123',
      },
    });
    expect(userLoginRes.status()).toBe(200);
    const userLoginData = await userLoginRes.json();
    userToken = userLoginData.token;
    expect(userToken).toBeDefined();
  });

  test.afterAll(async ({ request }) => {
    // Cleanup team if created
    if (createdTeamId) {
      await request.delete(`${BACKEND_URL}/api/admin/teams/${createdTeamId}`, {
        headers: { Authorization: `Bearer ${superadminToken}` },
      });
    }
    // Cleanup user if created
    if (createdUserId) {
      await request.delete(`${BACKEND_URL}/api/admin/users/${createdUserId}`, {
        headers: { Authorization: `Bearer ${superadminToken}` },
      });
    }
  });

  test('should fail with 401 when request is unauthenticated', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/api/admin/teams`);
    expect(res.status()).toBe(401);
  });

  test('should fail with 403 when regular user requests teams list', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/api/admin/teams`, {
      headers: {
        Authorization: `Bearer ${userToken}`,
      },
    });
    expect(res.status()).toBe(403);
  });

  test('should succeed when superadmin creates and lists teams', async ({ request }) => {
    // Create team
    const createRes = await request.post(`${BACKEND_URL}/api/admin/teams`, {
      headers: {
        Authorization: `Bearer ${superadminToken}`,
      },
      data: {
        name: testTeamName,
      },
    });
    expect(createRes.status()).toBe(200);
    const createData = await createRes.json();
    createdTeamId = createData.team_id;
    expect(createdTeamId).toBeDefined();

    // List teams
    const listRes = await request.get(`${BACKEND_URL}/api/admin/teams`, {
      headers: {
        Authorization: `Bearer ${superadminToken}`,
      },
    });
    expect(listRes.status()).toBe(200);
    const listData = await listRes.json();
    expect(listData.teams).toBeDefined();
    const names = listData.teams.map((t: any) => t.name);
    expect(names).toContain(testTeamName);
  });

  test('should succeed when superadmin adds, lists, and removes a member', async ({ request }) => {
    // Add member
    const addRes = await request.post(`${BACKEND_URL}/api/admin/members`, {
      headers: {
        Authorization: `Bearer ${superadminToken}`,
      },
      data: {
        team_id: createdTeamId,
        user_id: createdUserId,
        role: 'admin',
      },
    });
    expect(addRes.status()).toBe(200);

    // List members
    const listRes = await request.get(`${BACKEND_URL}/api/admin/members?team_id=${createdTeamId}`, {
      headers: {
        Authorization: `Bearer ${superadminToken}`,
      },
    });
    expect(listRes.status()).toBe(200);
    const listData = await listRes.json();
    expect(listData.members.length).toBe(1);
    expect(listData.members[0].user_id).toBe(createdUserId);
    expect(listData.members[0].role).toBe('admin');

    // Remove member
    const removeRes = await request.delete(
      `${BACKEND_URL}/api/admin/members?team_id=${createdTeamId}&user_id=${createdUserId}`,
      {
        headers: {
          Authorization: `Bearer ${superadminToken}`,
        },
      }
    );
    expect(removeRes.status()).toBe(200);
  });
});
