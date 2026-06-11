export function StreamingSkeleton() {
  return (
    <div className="flex gap-3 max-w-[85%] self-start">
      <div className="size-8 rounded-xl flex items-center justify-center flex-shrink-0 bg-muted ring-1 ring-border/50">
        <div className="size-[15px] rounded-full bg-foreground/30 animate-pulse" />
      </div>
      <div className="flex flex-col gap-2 max-w-xs flex-1">
        <div className="px-4 py-3 rounded-2xl rounded-tl-none border border-border/60 bg-card shadow-sm">
          <div className="flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-foreground/30 animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="size-1.5 rounded-full bg-foreground/30 animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="size-1.5 rounded-full bg-foreground/30 animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      </div>
    </div>
  );
}
