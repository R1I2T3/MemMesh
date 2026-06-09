import * as React from "react";
import { Button } from "@/components/ui/button";
import { AlertOctagon, RefreshCw } from "lucide-react";

interface Props {
  children?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Uncaught error in ErrorBoundary:", error, errorInfo);
  }

  private handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-16 text-foreground">
          <div className="mx-auto flex w-full max-w-md flex-col items-center text-center">
            <div className="rounded-full bg-destructive/10 p-4 text-destructive">
              <AlertOctagon className="h-12 w-12" />
            </div>
            <h1 className="mt-6 text-3xl font-bold tracking-tight">Something went wrong</h1>
            <p className="mt-4 text-muted-foreground text-center">
              An unexpected error occurred in the application. We've logged the issue and are looking into it.
            </p>
            {this.state.error && (
              <div className="mt-6 w-full overflow-hidden rounded-lg border border-border bg-muted/50 p-4 text-left font-mono text-xs text-muted-foreground max-h-48 overflow-y-auto">
                <p className="font-semibold text-destructive">{this.state.error.toString()}</p>
                {this.state.error.stack && (
                  <pre className="mt-2 whitespace-pre-wrap">{this.state.error.stack}</pre>
                )}
              </div>
            )}
            <div className="mt-8">
              <Button
                onClick={this.handleReload}
                className="flex items-center gap-2"
                size="lg"
              >
                <RefreshCw className="h-4 w-4" />
                Reload Page
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
