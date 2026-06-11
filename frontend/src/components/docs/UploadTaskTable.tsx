import { FileTextIcon, ActivityIcon } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import { StatusBadge } from '@/components/shared/StatusBadge';
import type { UploadTask } from '@/types/api';

interface UploadTaskTableProps {
  uploads: UploadTask[];
}

export function UploadTaskTable({ uploads }: UploadTaskTableProps) {
  return (
    <Card className="lg:col-span-2 border-border/80 shadow-sm bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <div className="flex items-center justify-center rounded-lg bg-amber-500/10 p-1.5 text-amber-600 dark:text-amber-400">
            <ActivityIcon className="size-4" />
          </div>
          Active Ingestions
        </CardTitle>
        <CardDescription className="text-[11px]">
          Celery task execution status.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {uploads.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground gap-2">
            <FileTextIcon className="size-8 opacity-30" />
            <span className="text-xs">No uploads in the current session.</span>
          </div>
        ) : (
          <div className="overflow-x-auto border border-border/60 rounded-xl">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[11px] font-semibold">Filename</TableHead>
                  <TableHead className="text-[11px] font-semibold">Task ID</TableHead>
                  <TableHead className="w-[120px] text-[11px] font-semibold">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {uploads.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-medium text-xs truncate max-w-[200px]" title={task.filename}>
                      {task.filename}
                    </TableCell>
                    <TableCell className="font-mono text-[10px] text-muted-foreground">
                      {task.taskId}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={task.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
