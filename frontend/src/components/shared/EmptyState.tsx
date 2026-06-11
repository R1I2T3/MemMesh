import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
}

export function EmptyState({ icon: Icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground gap-2 border border-dashed border-border/60 rounded-xl">
      <Icon className="size-8 opacity-30" />
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs leading-relaxed">{description}</p>
    </div>
  );
}
