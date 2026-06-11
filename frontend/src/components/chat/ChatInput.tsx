import { useState } from 'react';
import { SendIcon, Loader2Icon, GitBranchIcon, XIcon } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface ChatInputProps {
  onSend: (query: string, parentMsgId: string | null) => void;
  sendingQuery: boolean;
  parentMsgId: string | null;
  onCancelBranch: () => void;
}

export function ChatInput({ onSend, sendingQuery, parentMsgId, onCancelBranch }: ChatInputProps) {
  const [queryInput, setQueryInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim() || sendingQuery) return;
    onSend(queryInput, parentMsgId);
    setQueryInput('');
  };

  return (
    <div className="sticky bottom-0 bg-background/80 backdrop-blur-lg border-t border-border/50">
      <div className="max-w-3xl mx-auto px-4 py-3">
        {parentMsgId && (
          <div className="flex items-center justify-between bg-primary/8 border border-primary/15 text-primary px-3 py-2 rounded-xl mb-3 text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <GitBranchIcon className="size-3.5 shrink-0" />
              <span className="truncate">
                Branching from:{' '}
                <span className="font-mono font-semibold bg-primary/10 px-1.5 py-0.5 rounded text-[10px]">
                  {parentMsgId.substring(0, 8)}...
                </span>
              </span>
            </div>
            <Button
              size="icon-xs"
              variant="ghost"
              className="text-primary/60 hover:text-primary shrink-0 ml-2"
              onClick={onCancelBranch}
            >
              <XIcon className="size-3" />
            </Button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <Input
              placeholder="Ask anything, agent orchestrator will route your query..."
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              disabled={sendingQuery}
              className="flex-grow bg-background border-input/80 pr-10 h-10 text-sm rounded-xl focus-visible:ring-2 focus-visible:ring-primary/20 placeholder:text-muted-foreground/50"
            />
          </div>
          <Button
            type="submit"
            disabled={sendingQuery || !queryInput.trim()}
            size="icon"
            className="size-10 rounded-xl shrink-0 transition-all duration-200 active:scale-95 disabled:active:scale-100"
          >
            {sendingQuery ? (
              <Loader2Icon className="size-[18px] animate-spin" />
            ) : (
              <SendIcon className="size-[18px]" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}
