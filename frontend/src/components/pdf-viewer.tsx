import { Document, Page, pdfjs } from "react-pdf";
import { API_BASE } from "../lib/api";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Keep pdfjs-dist version in sync with the worker CDN URL below
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@4.8.69/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  docId: string;
  pageNumber?: number;
  bbox?: number[];
}

export function PdfViewer({ docId, pageNumber = 1, bbox }: PdfViewerProps) {
  const token = localStorage.getItem("token");
  const pdfUrl = token
    ? `${API_BASE}/api/documents/${docId}/pdf?token=${encodeURIComponent(token)}`
    : `${API_BASE}/api/documents/${docId}/pdf`;

  const scale = bbox?.every(v => v > 1.1) ? 600 / 612 : 600;
  const highlightStyle = bbox
    ? {
        left: `${Math.min(bbox[0], bbox[2]) * scale}px`,
        top: `${Math.min(bbox[1], bbox[3]) * scale}px`,
        width: `${Math.abs(bbox[2] - bbox[0]) * scale}px`,
        height: `${Math.abs(bbox[3] - bbox[1]) * scale}px`,
      }
    : null;

  return (
    <div className="relative overflow-auto border rounded-lg bg-white">
      <Document
        file={pdfUrl}
        loading={<div className="p-4 text-center">Loading PDF...</div>}
        error={
          <div className="p-4 text-center text-red-500">Failed to load PDF</div>
        }
      >
        <Page
          pageNumber={pageNumber}
          width={600}
          renderTextLayer={true}
          renderAnnotationLayer={true}
        />
      </Document>
      {highlightStyle && (
        <div
          className="absolute pointer-events-none border-2 border-indigo-500 bg-indigo-500/20"
          style={highlightStyle}
        />
      )}
    </div>
  );
}
