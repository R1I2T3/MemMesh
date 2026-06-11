export type Theme = 'light' | 'dark';

export function getNextTheme(current: Theme): Theme {
  return current === 'light' ? 'dark' : 'light';
}

export function applyTheme(theme: Theme): void {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  localStorage.setItem('theme', theme);
}

export function getSavedTheme(): Theme {
  return (localStorage.getItem('theme') as Theme) || 'light';
}
