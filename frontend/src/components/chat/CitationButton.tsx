interface CitationButtonProps {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
}

export function CitationButton({ children, onClick, title }: CitationButtonProps) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded-lg bg-accent text-accent-foreground hover:bg-indigo-100 dark:hover:bg-indigo-900/50 hover:text-indigo-700 dark:hover:text-indigo-400 transition-colors cursor-pointer align-baseline font-mono not-prose shadow-sm"
      title={title}
    >
      {children}
    </button>
  );
}
