import { createRoute } from '@tanstack/react-router';
import { Route as rootRoute } from './__root';
import { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import { formatHealthStatus } from '../utils/health';

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: LoginHome,
});

function LoginHome() {
  const [status, setStatus] = useState('Checking...');

  useEffect(() => {
    apiFetch('/api/health')
      .then(res => res.json())
      .then(data => {
        const health = formatHealthStatus(data.services || {});
        setStatus(health.overall);
      })
      .catch(() => setStatus('unreachable'));
  }, []);

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>MemMesh</h1>
      <p id="system-status">System: {status}</p>
      <h2>Login</h2>
    </div>
  );
}
