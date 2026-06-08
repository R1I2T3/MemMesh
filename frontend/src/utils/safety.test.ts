import { expect, test } from 'vitest';
import { clientSideInputCheck } from './safety';

test('clientSideInputCheck returns true for safe inputs', () => {
  expect(clientSideInputCheck('What is the weather today?')).toBe(true);
  expect(clientSideInputCheck('Give me details about project Titan')).toBe(true);
});

test('clientSideInputCheck returns false for SQL injection patterns', () => {
  expect(clientSideInputCheck('drop table users;')).toBe(false);
  expect(clientSideInputCheck('SELECT * FROM employees')).toBe(false);
  expect(clientSideInputCheck('DELETE FROM accounts')).toBe(false);
  expect(clientSideInputCheck('UNION SELECT password FROM admin')).toBe(false);
});
