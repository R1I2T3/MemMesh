import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CitationDrawer, Citation } from "./CitationDrawer";
import "@testing-library/jest-dom";

// Mock the Dialog/Sheet primitives from @base-ui/react to ensure smooth unit test execution
// since they can use portal components that require DOM setups.
vi.mock("@/components/ui/sheet", () => {
  return {
    Sheet: ({ children, open }: { children: React.ReactNode; open: boolean }) => (
      open ? <div data-testid="mock-sheet">{children}</div> : null
    ),
    SheetContent: ({ children, className }: { children: React.ReactNode; className?: string }) => (
      <div data-testid="mock-sheet-content" className={className}>{children}</div>
    ),
    SheetHeader: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="mock-sheet-header">{children}</div>
    ),
    SheetTitle: ({ children }: { children: React.ReactNode }) => (
      <h2 data-testid="mock-sheet-title">{children}</h2>
    ),
    SheetDescription: ({ children }: { children: React.ReactNode }) => (
      <p data-testid="mock-sheet-desc">{children}</p>
    ),
  };
});

describe("CitationDrawer Component", () => {
  const mockOnOpenChange = vi.fn();
  const mockClipboardWrite = vi.fn().mockImplementation(() => Promise.resolve());

  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: mockClipboardWrite,
      },
    });
  });

  const pdfCitation: Citation = {
    type: "pdf",
    content: "This is a sample document chunk content from a financial report.",
    source: "financial_report_2025.pdf",
    page: 12,
    bbox: [0.1, 0.2, 0.4, 0.35],
  };

  const webCitation: Citation = {
    type: "web",
    content: "This is a web search result snippet matching the user query.",
    source: "Google Search",
    url: "https://example.com/finance-report",
  };

  it("should render null when citation is null", () => {
    const { container } = render(
      <CitationDrawer isOpen={true} onOpenChange={mockOnOpenChange} citation={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("should render null when isOpen is false", () => {
    const { container } = render(
      <CitationDrawer isOpen={false} onOpenChange={mockOnOpenChange} citation={pdfCitation} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("should render PDF document citation details correctly", () => {
    render(
      <CitationDrawer isOpen={true} onOpenChange={mockOnOpenChange} citation={pdfCitation} />
    );

    // Verify header details
    expect(screen.getByTestId("mock-sheet-title")).toHaveTextContent("financial_report_2025.pdf");
    expect(screen.getByText("Document")).toBeInTheDocument();
    expect(screen.getByText("Page 12")).toBeInTheDocument();

    // Verify excerpt content
    expect(screen.getByText(/"This is a sample document chunk content from a financial report."/)).toBeInTheDocument();

    // Verify simulation details (PDF view)
    expect(screen.getByText("Page View (Simulated)")).toBeInTheDocument();
    expect(screen.getByText("bbox: [0.10, 0.20, 0.40, 0.35]")).toBeInTheDocument();
    expect(screen.getByText("Text Segment Highlighted")).toBeInTheDocument();
  });

  it("should render Web citation details correctly", () => {
    render(
      <CitationDrawer isOpen={true} onOpenChange={mockOnOpenChange} citation={webCitation} />
    );

    // Verify header details
    expect(screen.getByTestId("mock-sheet-title")).toHaveTextContent("Google Search");
    expect(screen.getByText("Web Search")).toBeInTheDocument();

    // Verify excerpt content
    expect(screen.getByText(/"This is a web search result snippet matching the user query."/)).toBeInTheDocument();

    // Verify URL link and browser simulation
    const link = screen.getByRole("link", { name: /https:\/\/example.com\/finance-report/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "https://example.com/finance-report");
    expect(link).toHaveAttribute("target", "_blank");

    expect(screen.getByText("Webpage View (Simulated)")).toBeInTheDocument();
    expect(screen.getAllByText("https://example.com/finance-report").length).toBeGreaterThan(0);
  });

  it("should copy the citation content when copy button is clicked", async () => {
    render(
      <CitationDrawer isOpen={true} onOpenChange={mockOnOpenChange} citation={pdfCitation} />
    );

    const copyBtn = screen.getByRole("button", { name: /copy/i });
    expect(copyBtn).toBeInTheDocument();

    fireEvent.click(copyBtn);

    expect(mockClipboardWrite).toHaveBeenCalledWith(pdfCitation.content);
    
    // Check if the text changes to Copied!
    const copiedText = await screen.findByText(/copied!/i);
    expect(copiedText).toBeInTheDocument();
  });
});
