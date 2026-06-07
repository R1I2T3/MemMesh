export function getNextTheme(current: string): string {
  return current === 'light' ? 'dark' : 'light';
}

export function applyTheme(theme: string): void {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  localStorage.setItem('theme', theme);
}

export function getSavedTheme(): string {
  return localStorage.getItem('theme') || 'light';
}
