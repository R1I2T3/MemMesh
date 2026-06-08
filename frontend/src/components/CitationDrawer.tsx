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

export interface Citation {
  type?: "pdf" | "web" | string;
  content: string;
  source?: string;
  page?: number;
  bbox?: number[]; // [x1, y1, x2, y2] - can be normalized (0..1) or absolute points
  url?: string;
}

interface CitationDrawerProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  citation: Citation | null;
}

// Deterministic mockup of lines on a document page (y is % from top, start/end are % from left)
const MOCK_PAGE_LINES = [
  { y: 8, start: 8, end: 75 },
  { y: 12, start: 8, end: 92 },
  { y: 16, start: 8, end: 85 },
  { y: 20, start: 8, end: 45 },

  { y: 28, start: 8, end: 88 },
  { y: 32, start: 8, end: 90 },
  { y: 36, start: 8, end: 80 },
  { y: 40, start: 8, end: 70 },
  { y: 44, start: 8, end: 35 },

  { y: 52, start: 8, end: 92 },
  { y: 56, start: 8, end: 87 },
  { y: 60, start: 8, end: 90 },
  { y: 64, start: 8, end: 55 },

  { y: 72, start: 8, end: 80 },
  { y: 76, start: 8, end: 75 },
  { y: 80, start: 8, end: 85 },
  { y: 84, start: 8, end: 40 },

  { y: 90, start: 8, end: 85 },
  { y: 94, start: 8, end: 60 },
];

export function CitationDrawer({ isOpen, onOpenChange, citation }: CitationDrawerProps) {
  const [copied, setCopied] = React.useState(false);

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

  // Helper to normalize bbox coordinates to percentages
  const getNormalizedCoords = (bbox: number[] | undefined) => {
    if (!bbox || bbox.length < 4) {
      // Return a default mockup highlight if no bbox is provided
      return { x: 8, y: 28, w: 84, h: 20 };
    }

    let [x1, y1, x2, y2] = bbox;
    const maxVal = Math.max(x1, y1, x2, y2);

    if (maxVal > 1.1) {
      // Standard PDF point dimensions (typically letter 612x792 or A4 595x842)
      // We will normalize using standard page size assumptions
      const assumedWidth = 612;
      const assumedHeight = 792;
      x1 = (x1 / assumedWidth) * 100;
      x2 = (x2 / assumedWidth) * 100;
      y1 = (y1 / assumedHeight) * 100;
      y2 = (y2 / assumedHeight) * 100;
    } else {
      // Already normalized values between 0 and 1
      x1 = x1 * 100;
      x2 = x2 * 100;
      y1 = y1 * 100;
      y2 = y2 * 100;
    }

    const x = Math.min(x1, x2);
    const y = Math.min(y1, y2);
    const w = Math.abs(x2 - x1);
    const h = Math.abs(y2 - y1);

    return {
      x: Math.max(0, Math.min(95, x)),
      y: Math.max(0, Math.min(95, y)),
      w: Math.max(5, Math.min(100 - x, w)),
      h: Math.max(5, Math.min(100 - y, h)),
    };
  };

  const highlight = getNormalizedCoords(citation.bbox);

  // Helper to check if a mock line intersects vertically with the highlight bounding box
  const isLineHighlighted = (lineY: number) => {
    return lineY >= highlight.y && lineY <= highlight.y + highlight.h;
  };

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
                  Page View (Simulated)
                </h3>
                {citation.bbox && (
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                    bbox: [{citation.bbox.map(n => n.toFixed(2)).join(", ")}]
                  </span>
                )}
              </div>

              {/* Simulated PDF container */}
              <div className="flex justify-center">
                <div className="relative w-full max-w-[280px] aspect-[1/1.414] bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl shadow-md overflow-hidden p-6 select-none group">
                  {/* Watermark grid background */}
                  <div className="absolute inset-0 grid grid-cols-6 grid-rows-8 opacity-[0.02] pointer-events-none">
                    {Array.from({ length: 48 }).map((_, i) => (
                      <div key={i} className="border border-slate-900" />
                    ))}
                  </div>

                  {/* SVG Document lines */}
                  <svg
                    viewBox="0 0 100 141.4"
                    className="w-full h-full"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    {/* Bounding Box Highlight Rect */}
                    <rect
                      x={highlight.x}
                      y={highlight.y}
                      width={highlight.w}
                      height={highlight.h}
                      rx="1"
                      className="fill-indigo-600/15 stroke-indigo-600 dark:fill-indigo-400/20 dark:stroke-indigo-400 animate-pulse"
                      strokeWidth="0.8"
                      strokeDasharray="1, 0.5"
                    />

                    {/* Simulated Text Lines */}
                    {MOCK_PAGE_LINES.map((line, idx) => {
                      const highlighted = isLineHighlighted(line.y);
                      return (
                        <line
                          key={idx}
                          x1={line.start}
                          y1={line.y}
                          x2={line.end}
                          y2={line.y}
                          strokeWidth="1.2"
                          strokeLinecap="round"
                          className={
                            highlighted
                              ? "stroke-indigo-600/70 dark:stroke-indigo-400/70"
                              : "stroke-slate-200 dark:stroke-slate-800"
                          }
                        />
                      );
                    })}
                  </svg>

                  {/* PDF Bounding Box Hover Tag */}
                  <div className="absolute inset-0 bg-transparent flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none duration-300">
                    <div className="bg-indigo-600/90 text-white text-[10px] px-2 py-1 rounded shadow-lg font-medium tracking-wide">
                      Text Segment Highlighted
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
