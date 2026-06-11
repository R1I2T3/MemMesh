import { expect, test } from 'vitest';
import { getNextTheme } from './theme';

test('toggles theme correctly', () => {
  expect(getNextTheme('light')).toBe('dark');
  expect(getNextTheme('dark')).toBe('light');
});
