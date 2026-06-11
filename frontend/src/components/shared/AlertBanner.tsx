import { AlertTriangleIcon, CheckCircle2Icon } from 'lucide-react';

interface AlertBannerProps {
  type: 'error' | 'success';
  message: string;
}

export function AlertBanner({ type, message }: AlertBannerProps) {
  if (!message) return null;
  return (
    <div
      className={`flex items-center gap-2 p-3 rounded-xl text-xs transition-all duration-200 ${
        type === 'error'
          ? 'bg-destructive/8 text-destructive border border-destructive/15'
          : 'bg-emerald-500/8 text-emerald-600 dark:text-emerald-400 border border-emerald-500/15'
      }`}
      role="alert"
    >
      {type === 'error' ? (
        <AlertTriangleIcon className="size-4 shrink-0" />
      ) : (
        <CheckCircle2Icon className="size-4 shrink-0" />
      )}
      <span>{message}</span>
    </div>
  );
}
