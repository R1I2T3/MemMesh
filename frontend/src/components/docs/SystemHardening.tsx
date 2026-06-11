import { HardDriveIcon, Loader2Icon } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertBanner } from '@/components/shared/AlertBanner';

interface TaskState {
  taskId: string;
  status: string;
  result: any;
  loading: boolean;
}

interface SystemHardeningProps {
  decay: TaskState;
  drift: TaskState;
  error: string;
  onTriggerDecay: () => void;
  onTriggerDrift: () => void;
}

function TaskCard({
  title,
  description,
  buttonLabel,
  buttonColor,
  task,
  onTrigger,
  triggerBtnId,
  taskIdId,
  taskStatusId,
}: {
  title: string;
  description: string;
  buttonLabel: string;
  buttonColor: string;
  task: TaskState;
  onTrigger: () => void;
  triggerBtnId?: string;
  taskIdId?: string;
  taskStatusId?: string;
}) {
  return (
    <div className="p-4 border border-border/60 rounded-xl bg-background/50 flex flex-col gap-3">
      <div className="flex justify-between items-start gap-3">
        <div className="min-w-0">
          <h4 className="font-semibold text-xs text-foreground">{title}</h4>
          <p className="text-[10px] text-muted-foreground mt-0.5">{description}</p>
        </div>
        <Button
          id={triggerBtnId}
          onClick={onTrigger}
          disabled={task.loading || (task.status !== '' && task.status !== 'SUCCESS' && task.status !== 'FAILED')}
          size="xs"
          className={`${buttonColor} shrink-0`}
        >
          {task.loading ? <Loader2Icon className="size-3 animate-spin" /> : buttonLabel}
        </Button>
      </div>
      {task.taskId && (
        <div className="text-[10px] space-y-1 bg-muted/50 p-2.5 rounded-lg border border-border/40">
          <div>
            <span className="font-semibold text-muted-foreground">Task ID:</span>{' '}
            <span id={taskIdId} className="font-mono text-foreground/70">{task.taskId}</span>
          </div>
          <div>
            <span className="font-semibold text-muted-foreground">Status:</span>{' '}
            <span id={taskStatusId} className="font-mono text-foreground/70">{task.status}</span>
          </div>
          {task.result && title.toLowerCase().includes('decay') && (
            <div>
              <span className="font-semibold text-muted-foreground">Processed:</span>{' '}
              {task.result.processed_teams} team(s)
            </div>
          )}
          {task.result && title.toLowerCase().includes('drift') && (
            <div className="space-y-1">
              <div>
                <span className="font-semibold text-muted-foreground">Drift Detected:</span>{' '}
                <span
                  className={
                    task.result.drift_detected
                      ? 'text-destructive font-bold'
                      : 'text-emerald-500 font-bold'
                  }
                >
                  {task.result.drift_detected ? 'Yes' : 'No'}
                </span>
              </div>
              {task.result.metrics && (
                <div className="grid grid-cols-2 gap-1 text-[10px] text-muted-foreground">
                  <div>
                    Avg Len: {task.result.metrics.avg_length_last?.toFixed(1)} vs{' '}
                    {task.result.metrics.avg_length_prev?.toFixed(1)}
                  </div>
                  <div>
                    Avg Rating: {task.result.metrics.avg_rating_last?.toFixed(1)} vs{' '}
                    {task.result.metrics.avg_rating_prev?.toFixed(1)}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function SystemHardening({ decay, drift, error, onTriggerDecay, onTriggerDrift }: SystemHardeningProps) {
  return (
    <Card className="border-border/80 shadow-sm bg-card" id="system-hardening-card">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <div className="flex items-center justify-center rounded-lg bg-amber-500/10 p-1.5 text-amber-600 dark:text-amber-400">
            <HardDriveIcon className="size-4" />
          </div>
          System Hardening & Optimization
        </CardTitle>
        <CardDescription className="text-[11px]">
          Trigger maintenance tasks to keep vector databases and graph databases pruned.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error && <AlertBanner type="error" message={error} />}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <TaskCard
            title="Memory Decay Weighting"
            description="Prunes low-importance graph entities and scales Weaviate weights."
            buttonLabel="Trigger Decay"
            buttonColor="bg-amber-600 hover:bg-amber-700 text-white font-semibold"
            task={decay}
            onTrigger={onTriggerDecay}
            triggerBtnId="trigger-decay-btn"
            taskIdId="decay-task-id"
            taskStatusId="decay-task-status"
          />
          <TaskCard
            title="Semantic Drift Detection"
            description="Analyzes query statistics and ratings to evaluate domain changes."
            buttonLabel="Trigger Drift"
            buttonColor="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold"
            task={drift}
            onTrigger={onTriggerDrift}
            triggerBtnId="trigger-drift-btn"
            taskIdId="drift-task-id"
            taskStatusId="drift-task-status"
          />
        </div>
      </CardContent>
    </Card>
  );
}
