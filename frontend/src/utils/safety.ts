const SQL_PATTERNS = [/drop\s+table/i, /select\s+\*/i, /delete\s+from/i, /union\s+select/i];

export function clientSideInputCheck(query: string): boolean {
  return !SQL_PATTERNS.some(p => p.test(query));
}
