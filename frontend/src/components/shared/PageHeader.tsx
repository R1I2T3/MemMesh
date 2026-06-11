import type { LucideIcon } from 'lucide-react';

interface PageHeaderProps {
  icon: LucideIcon;
  title: string;
  description: string;
}

export function PageHeader({ icon: Icon, title, description }: PageHeaderProps) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center justify-center rounded-xl bg-primary/10 p-2.5 text-primary">
        <Icon className="size-5" />
      </div>
      <div className="flex flex-col gap-0.5">
        <h1 className="text-xl font-bold tracking-tight">{title}</h1>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
