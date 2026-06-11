import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertOctagonIcon, RefreshCwIcon } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-background p-6">
          <div className="flex flex-col items-center gap-5 max-w-sm text-center">
            <div className="bg-destructive/10 p-4 rounded-2xl ring-1 ring-destructive/20">
              <AlertOctagonIcon className="size-10 text-destructive" />
            </div>
            <div className="flex flex-col gap-1">
              <h1 className="text-lg font-semibold tracking-tight text-foreground">Something went wrong</h1>
              <p className="text-xs text-muted-foreground leading-relaxed">
                An unexpected error occurred. Please reload the page to continue.
              </p>
            </div>
            {this.state.error && (
              <div className="w-full rounded-xl border border-border/60 bg-muted/30 p-4 text-left">
                <p className="font-mono text-[10px] text-muted-foreground break-all leading-relaxed">
                  {this.state.error.message}
                </p>
              </div>
            )}
            <button
              onClick={this.handleReload}
              className="inline-flex items-center gap-2 rounded-xl bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:bg-primary/90 active:scale-[0.98]"
            >
              <RefreshCwIcon className="size-4" />
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
