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
  bbox?: number[]; // [x1, y1, x2, y2] - can be normalized (0..1) or absolute points
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
      <SheetContent className="w-full sm:max-w-md h-full flex flex-col p-0 border-l border-slate-200 dark:border-slate-800 bg-background shadow-2xl transition-all duration-300">
        <SheetHeader className="p-6 border-b border-slate-100 dark:border-slate-900">
          <div className="flex items-center gap-2 mb-2">
            {isWeb ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-900/50">
                <GlobeIcon className="size-3" />
                Web Search
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-950/30 dark:text-indigo-400 dark:border-indigo-900/50">
                <FileTextIcon className="size-3" />
                Document
              </span>
            )}
            {!isWeb && citation.page !== undefined && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700">
                Page {citation.page}
              </span>
            )}
          </div>
          <SheetTitle className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-100 break-words pr-8">
            {displayName}
          </SheetTitle>
          <SheetDescription className="text-xs text-muted-foreground mt-1">
            Citation Details & Source Excerpt
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Excerpt Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Source Excerpt
              </h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 flex items-center gap-1"
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
            <div className="relative p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-sans whitespace-pre-wrap select-text">
                "{citation.content}"
              </p>
            </div>
          </div>

          {/* Web Details vs. PDF Document Visual Simulator */}
          {isWeb ? (
            <div className="space-y-4">
              {/* Web URL Info */}
              {citation.url && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Source Link
                  </h4>
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white hover:bg-slate-50 dark:bg-slate-900 dark:hover:bg-slate-800/80 text-sm font-medium text-indigo-600 dark:text-indigo-400 w-full transition-colors group"
                  >
                    <GlobeIcon className="size-4 shrink-0" />
                    <span className="truncate flex-1 text-left">{citation.url}</span>
                    <ExternalLinkIcon className="size-4 shrink-0 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                  </a>
                </div>
              )}

              {/* simulated browser preview */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Webpage View (Simulated)
                </h4>
                <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-inner bg-slate-50 dark:bg-slate-900/30">
                  {/* Browser Address Bar */}
                  <div className="bg-slate-100 dark:bg-slate-900 p-2 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="size-2.5 rounded-full bg-rose-400" />
                      <div className="size-2.5 rounded-full bg-amber-400" />
                      <div className="size-2.5 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 bg-white dark:bg-slate-950 px-2 py-0.5 rounded text-[10px] text-slate-500 font-mono truncate select-all border border-slate-200/60 dark:border-slate-800/60">
                      {citation.url || "https://web-source.info/context"}
                    </div>
                  </div>

                  {/* Simulated Webpage Content */}
                  <div className="p-4 bg-white dark:bg-slate-950 aspect-[4/3] flex flex-col gap-3 relative">
                    <div className="h-4 w-1/3 bg-slate-200 dark:bg-slate-800 rounded" />
                    <div className="space-y-2">
                      <div className="h-2.5 w-full bg-slate-100 dark:bg-slate-900 rounded" />
                      <div className="h-2.5 w-full bg-slate-100 dark:bg-slate-900 rounded" />
                      {/* Highlighted Match Box */}
                      <div className="p-2.5 bg-emerald-50 dark:bg-emerald-950/20 border-l-2 border-emerald-500 rounded-r text-[11px] text-emerald-800 dark:text-emerald-400 font-sans leading-relaxed select-none">
                        {citation.content.substring(0, 120)}
                        {citation.content.length > 120 ? "..." : ""}
                      </div>
                      <div className="h-2.5 w-5/6 bg-slate-100 dark:bg-slate-900 rounded" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Document View
                </h3>
                {citation.bbox && (
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
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
                    className="w-full"
                  >
                    {showPdf ? "Hide PDF" : "View in Document"}
                  </Button>
                  {showPdf && (
                    <div className="max-h-96 overflow-auto rounded-lg border">
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
