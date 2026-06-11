import { HardDriveIcon, FileTextIcon, Loader2Icon } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import type { DocumentItem } from '@/types/api';

interface DocumentTableProps {
  documents: DocumentItem[];
  loading: boolean;
}

export function DocumentTable({ documents, loading }: DocumentTableProps) {
  return (
    <Card className="border-border/80 shadow-sm bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <div className="flex items-center justify-center rounded-lg bg-emerald-500/10 p-1.5 text-emerald-600 dark:text-emerald-400">
            <HardDriveIcon className="size-4" />
          </div>
          Ingested Documents
        </CardTitle>
        <CardDescription className="text-[11px]">
          Successfully processed files available for search and graph retrieval.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center p-8">
            <Loader2Icon className="size-6 animate-spin text-muted-foreground/50" />
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground gap-2">
            <FileTextIcon className="size-8 opacity-30" />
            <span className="text-xs">No ingested documents found for this team.</span>
          </div>
        ) : (
          <div className="overflow-x-auto border border-border/60 rounded-xl">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[11px] font-semibold">Filename</TableHead>
                  <TableHead className="text-[11px] font-semibold">Document ID</TableHead>
                  <TableHead className="w-[100px] text-[11px] font-semibold">Version</TableHead>
                  <TableHead className="w-[200px] text-[11px] font-semibold">Ingested At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow key={doc.parent_id}>
                    <TableCell className="font-medium text-xs">{doc.filename}</TableCell>
                    <TableCell className="font-mono text-[10px] text-muted-foreground">
                      {doc.parent_id}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      v{doc.version_number}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {doc.created_at ? new Date(doc.created_at).toLocaleString() : 'N/A'}
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
