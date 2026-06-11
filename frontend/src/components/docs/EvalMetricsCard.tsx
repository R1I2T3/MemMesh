import { ActivityIcon, Loader2Icon, AlertTriangleIcon } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { AlertBanner } from '@/components/shared/AlertBanner';

interface EvalResult {
  feedback_id: string;
  query: string;
  response: string;
  rating: number;
  faithfulness_score: number;
  relevancy_score: number;
  reason: string;
}

interface EvalMetricsCardProps {
  results: EvalResult[] | null;
  running: boolean;
  error: string;
  onRun: () => void;
}

export function EvalMetricsCard({ results, running, error, onRun }: EvalMetricsCardProps) {
  const isSkipped = results && 'status' in results && (results as any).status === 'skipped';

  return (
    <Card className="border-border/80 shadow-sm bg-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <div className="flex items-center justify-center rounded-lg bg-indigo-500/10 p-1.5 text-indigo-600 dark:text-indigo-400">
              <ActivityIcon className="size-4" />
            </div>
            DeepEval Metrics & RLHF Evaluation
          </CardTitle>
          <Button
            id="run-eval-btn"
            onClick={onRun}
            disabled={running}
            size="sm"
            className="h-8 text-xs font-medium gap-1.5"
          >
            {running ? (
              <>
                <Loader2Icon className="size-3.5 animate-spin" />
                <span>Evaluating...</span>
              </>
            ) : (
              <span>Run DeepEval Metrics</span>
            )}
          </Button>
        </div>
        <CardDescription className="text-[11px]">
          Evaluate user feedback query-response pairs against DeepEval's Faithfulness and Answer Relevancy metrics.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error && <AlertBanner type="error" message={error} />}

        {results && isSkipped ? (
          <div className="flex items-center gap-2 p-3 rounded-xl text-xs bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/15">
            <AlertTriangleIcon className="size-4 shrink-0" />
            <span>No user feedback ratings found to evaluate. Submit some feedback in Chat first.</span>
          </div>
        ) : results ? (
          <div className="overflow-x-auto border border-border/60 rounded-xl">
            <Table id="eval-results-table">
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[11px] font-semibold">Feedback ID</TableHead>
                  <TableHead className="text-[11px] font-semibold">Query</TableHead>
                  <TableHead className="text-[11px] font-semibold">Response</TableHead>
                  <TableHead className="w-[80px] text-center text-[11px] font-semibold">Rating</TableHead>
                  <TableHead className="w-[120px] text-center text-[11px] font-semibold">Faithfulness</TableHead>
                  <TableHead className="w-[120px] text-center text-[11px] font-semibold">Relevancy</TableHead>
                  <TableHead className="text-[11px] font-semibold">Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((result) => (
                  <TableRow key={result.feedback_id} className="eval-result-row">
                    <TableCell className="font-mono text-[10px] text-muted-foreground truncate max-w-[80px]" title={result.feedback_id}>
                      {result.feedback_id.substring(0, 8)}...
                    </TableCell>
                    <TableCell className="truncate max-w-[150px] text-xs" title={result.query}>
                      {result.query}
                    </TableCell>
                    <TableCell className="truncate max-w-[200px] text-xs" title={result.response}>
                      {result.response}
                    </TableCell>
                    <TableCell className="text-center">
                      {result.rating === 1 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold font-mono">
                          +1
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-red-500/10 text-red-500 text-[10px] font-semibold font-mono">
                          -1
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-center font-mono font-semibold text-primary text-xs">
                      {(result.faithfulness_score * 100).toFixed(0)}%
                    </TableCell>
                    <TableCell className="text-center font-mono font-semibold text-primary text-xs">
                      {(result.relevancy_score * 100).toFixed(0)}%
                    </TableCell>
                    <TableCell className="text-[10px] text-muted-foreground" title={result.reason}>
                      {result.reason}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
