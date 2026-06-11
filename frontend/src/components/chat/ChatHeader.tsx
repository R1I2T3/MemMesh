import { ChevronLeftIcon, ChevronRightIcon, FileDownIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ChatHeaderProps {
  activeSessionId: string;
  threadPosition: string;
  hasMultipleThreads: boolean;
  onPrevThread: () => void;
  onNextThread: () => void;
  onExport: (format: 'md' | 'json') => void;
}

export function ChatHeader({
  activeSessionId,
  threadPosition,
  hasMultipleThreads,
  onPrevThread,
  onNextThread,
  onExport,
}: ChatHeaderProps) {
  return (
    <div className="px-5 py-3 border-b border-border/50 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-background/50">
      <div className="min-w-0">
        <h2 id="chat-title" className="text-sm font-semibold tracking-tight">
          Chat Interface
        </h2>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Session: <span className="font-mono text-primary font-medium text-[10px]">{activeSessionId}</span>
        </p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {hasMultipleThreads && (
          <div className="flex items-center gap-1.5 border border-border/60 bg-background px-2.5 py-1 rounded-lg text-[11px]">
            <span className="font-medium text-muted-foreground">Threads:</span>
            <span className="font-mono text-foreground/80">{threadPosition}</span>
            <div className="flex items-center gap-0.5 ml-0.5">
              <Button size="icon-xs" variant="ghost" onClick={onPrevThread}>
                <ChevronLeftIcon className="size-3" />
              </Button>
              <Button size="icon-xs" variant="ghost" onClick={onNextThread}>
                <ChevronRightIcon className="size-3" />
              </Button>
            </div>
          </div>
        )}
        <Button variant="outline" size="xs" onClick={() => onExport('md')} className="h-7 gap-1">
          <FileDownIcon className="size-3" />
          MD
        </Button>
        <Button variant="outline" size="xs" onClick={() => onExport('json')} className="h-7 gap-1">
          <FileDownIcon className="size-3" />
          JSON
        </Button>
      </div>
    </div>
  );
}
