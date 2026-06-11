import * as React from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  FileTextIcon,
  GlobeIcon,
  ExternalLinkIcon,
  CopyIcon,
  CheckIcon,
} from "lucide-react";
import { PdfViewer } from "./pdf-viewer";

export interface Citation {
  type?: "pdf" | "web" | string;
  content: string;
  source?: string;
  page?: number;
  page_number?: number;
  bbox?: number[];
  url?: string;
  parent_id?: string;
}

interface CitationDrawerProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  citation: Citation | null;
}

export function CitationDrawer({ isOpen, onOpenChange, citation }: CitationDrawerProps) {
  const [copied, setCopied] = React.useState(false);
  const [showPdf, setShowPdf] = React.useState(false);

  const handleCopy = () => {
    if (!citation) return;
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(citation.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } else {
      console.warn("Clipboard API not available in this environment.");
    }
  };

  if (!citation) return null;

  const isWeb = citation.type === "web" || !!citation.url;
  const displayName = citation.source || (isWeb ? "Web Source" : "Document.pdf");

  return (
    <Sheet open={isOpen} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg h-full flex flex-col p-0 border-l border-border bg-background shadow-xl">
        <SheetHeader className="p-5 border-b border-border/50">
          <div className="flex items-center gap-2 mb-2">
            {isWeb ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-900/50">
                <GlobeIcon className="size-3" />
                Web Search
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-950/30 dark:text-indigo-400 dark:border-indigo-900/50">
                <FileTextIcon className="size-3" />
                Document
              </span>
            )}
            {!isWeb && citation.page !== undefined && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground border border-border">
                Page {citation.page}
              </span>
            )}
          </div>
          <SheetTitle className="text-lg font-semibold tracking-tight text-foreground break-words pr-8">
            {displayName}
          </SheetTitle>
          <SheetDescription className="text-[11px] text-muted-foreground mt-0.5">
            Citation Details & Source Excerpt
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Excerpt Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-[0.1em]">
                Source Excerpt
              </h3>
              <Button
                variant="ghost"
                size="xs"
                className="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground gap-1"
                onClick={handleCopy}
              >
                {copied ? (
                  <>
                    <CheckIcon className="size-3 text-emerald-500" />
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <CopyIcon className="size-3" />
                    <span>Copy</span>
                  </>
                )}
              </Button>
            </div>
            <div className="relative p-4 rounded-xl border border-border/60 bg-muted/30">
              <p className="text-sm text-foreground/80 leading-relaxed font-sans whitespace-pre-wrap select-text">
                "{citation.content}"
              </p>
            </div>
          </div>

          {/* Web Details vs. PDF */}
          {isWeb ? (
            <div className="space-y-4">
              {citation.url && (
                <div className="space-y-2">
                  <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-[0.1em]">
                    Source Link
                  </h4>
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-border/60 bg-card hover:bg-muted/50 text-sm font-medium text-primary w-full transition-colors group"
                  >
                    <GlobeIcon className="size-4 shrink-0" />
                    <span className="truncate flex-1 text-left">{citation.url}</span>
                    <ExternalLinkIcon className="size-4 shrink-0 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                  </a>
                </div>
              )}

              <div className="space-y-2">
                <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-[0.1em]">
                  Webpage View (Simulated)
                </h4>
                <div className="border border-border/60 rounded-xl overflow-hidden shadow-inner bg-muted/20">
                  <div className="bg-muted/50 p-2 border-b border-border/60 flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="size-2.5 rounded-full bg-rose-400" />
                      <div className="size-2.5 rounded-full bg-amber-400" />
                      <div className="size-2.5 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 bg-background px-2 py-0.5 rounded text-[10px] text-muted-foreground font-mono truncate select-all border border-border/30">
                      {citation.url || "https://web-source.info/context"}
                    </div>
                  </div>
                  <div className="p-4 bg-background aspect-[4/3] flex flex-col gap-3 relative">
                    <div className="h-4 w-1/3 bg-muted rounded" />
                    <div className="space-y-2">
                      <div className="h-2.5 w-full bg-muted/50 rounded" />
                      <div className="h-2.5 w-full bg-muted/50 rounded" />
                      <div className="p-2.5 bg-emerald-50 dark:bg-emerald-950/20 border-l-2 border-emerald-500 rounded-r text-[11px] text-emerald-800 dark:text-emerald-400 font-sans leading-relaxed select-none">
                        {citation.content.substring(0, 120)}
                        {citation.content.length > 120 ? "..." : ""}
                      </div>
                      <div className="h-2.5 w-5/6 bg-muted/50 rounded" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-[0.1em]">
                  Document View
                </h3>
                {citation.bbox && (
                  <span className="text-[10px] font-mono text-muted-foreground/60 bg-muted/50 px-1.5 py-0.5 rounded">
                    bbox: [{citation.bbox.map(n => n.toFixed(2)).join(", ")}]
                  </span>
                )}
              </div>

              {citation.parent_id && (
                <div className="space-y-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowPdf(!showPdf)}
                    className="w-full h-8 text-xs"
                  >
                    {showPdf ? "Hide PDF" : "View in Document"}
                  </Button>
                  {showPdf && (
                    <div className="max-h-96 overflow-auto rounded-xl border border-border/60">
                      <PdfViewer
                        docId={citation.parent_id}
                        pageNumber={citation.page_number || citation.page || 1}
                        bbox={citation.bbox}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
