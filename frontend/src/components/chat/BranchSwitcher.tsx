import { GitBranchIcon, ChevronLeftIcon, ChevronRightIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface BranchSwitcherProps {
  currentIndex: number;
  totalBranches: number;
  isUser: boolean;
  onPrev: () => void;
  onNext: () => void;
}

export function BranchSwitcher({ currentIndex, totalBranches, isUser, onPrev, onNext }: BranchSwitcherProps) {
  if (totalBranches <= 1) return null;

  return (
    <div className={`flex items-center gap-2 text-[10px] ${isUser ? 'justify-end mr-11' : 'justify-start ml-11'}`}>
      <div className="flex items-center gap-1.5 border border-border/50 rounded-lg bg-background/80 px-2.5 py-1 shadow-sm">
        <GitBranchIcon className="size-2.5 text-muted-foreground/50" />
        <span className="font-medium text-muted-foreground/70">Branch:</span>
        <span className="font-mono text-foreground/60">
          {currentIndex + 1}/{totalBranches}
        </span>
        <div className="flex items-center gap-0.5 ml-0.5">
          <Button size="icon-xs" variant="ghost" onClick={onPrev}>
            <ChevronLeftIcon className="size-2.5" />
          </Button>
          <Button size="icon-xs" variant="ghost" onClick={onNext}>
            <ChevronRightIcon className="size-2.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
