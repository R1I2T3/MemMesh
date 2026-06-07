import { expect, test } from 'vitest';
import { formatHealthStatus } from './health';

test('formats all health statuses correctly', () => {
  expect(formatHealthStatus({ mysql: 'ok', weaviate: 'ok', neo4j: 'ok', redis: 'ok' }))
    .toEqual({ overall: 'operational', services: 4, healthy: 4 });

  expect(formatHealthStatus({ mysql: 'ok', weaviate: 'error', neo4j: 'ok', redis: 'ok' }))
    .toEqual({ overall: 'degraded', services: 4, healthy: 3 });
});
