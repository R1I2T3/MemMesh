import { Document, Page, pdfjs } from "react-pdf";
import { API_BASE } from "../lib/api";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@4.8.69/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  docId: string;
  pageNumber?: number;
  bbox?: number[];
}

export function PdfViewer({ docId, pageNumber = 1, bbox }: PdfViewerProps) {
  const highlightStyle = bbox
    ? {
        left: `${Math.min(bbox[0], bbox[2])}px`,
        top: `${Math.min(bbox[1], bbox[3])}px`,
        width: `${Math.abs(bbox[2] - bbox[0])}px`,
        height: `${Math.abs(bbox[3] - bbox[1])}px`,
      }
    : null;

  return (
    <div className="relative overflow-auto border rounded-lg bg-white">
      <Document
        file={`${API_BASE}/api/documents/${docId}/pdf`}
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
