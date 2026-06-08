import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { useState, useEffect, useRef, useCallback } from 'react';
import { apiFetch } from '../lib/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { UploadIcon, Loader2Icon, FileTextIcon, CheckCircle2Icon, XCircleIcon, AlertTriangleIcon } from 'lucide-react';
import { validateFile, normalizeUploadStatus } from '../utils/upload';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/docs',
  component: DocumentIngestionConsole,
});

interface Team {
  team_id: string;
  name: string;
}

interface DocumentItem {
  parent_id: string;
  filename: string;
  created_at: string | null;
}

interface UploadTask {
  id: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  taskId: string;
}

function AlertBanner({ type, message }: { type: 'error' | 'success'; message: string }) {
  if (!message) return null;
  return (
    <div
      className={`flex items-center gap-2 p-3 rounded-lg text-sm transition-all duration-200 ${
        type === 'error'
          ? 'bg-destructive/10 text-destructive border border-destructive/20'
          : 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
      }`}
      role="alert"
    >
      {type === 'error' ? <AlertTriangleIcon className="size-4 shrink-0" /> : <CheckCircle2Icon className="size-4 shrink-0" />}
      <span>{message}</span>
    </div>
  );
}

function DocumentIngestionConsole() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeTeamId, setActiveTeamId] = useState<string>(() => {
    return localStorage.getItem('active_team_id') || '';
  });
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [uploads, setUploads] = useState<UploadTask[]>([]);
  
  // Loading & UI States
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch teams
  const fetchTeams = useCallback(async () => {
    setLoadingTeams(true);
    try {
      const res = await apiFetch('/api/teams');
      if (res.ok) {
        const data = await res.json();
        const teamsList: Team[] = data.teams || [];
        setTeams(teamsList);
        // Automatically select first team if none is selected
        if (teamsList.length > 0 && !activeTeamId) {
          const firstId = teamsList[0].team_id;
          setActiveTeamId(firstId);
          localStorage.setItem('active_team_id', firstId);
        }
      }
    } catch {
      setError('Failed to load teams');
    } finally {
      setLoadingTeams(false);
    }
  }, [activeTeamId]);

  // Fetch documents for active team
  const fetchDocuments = useCallback(async (teamId: string) => {
    if (!teamId) return;
    setLoadingDocs(true);
    try {
      const res = await apiFetch('/api/documents', {
        headers: {
          'X-Active-Team-ID': teamId,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      } else {
        setDocuments([]);
      }
    } catch {
      setError('Failed to fetch documents list');
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  // Run on mount
  useEffect(() => {
    fetchTeams();
  }, [fetchTeams]);

  // Fetch docs when active team changes
  useEffect(() => {
    if (activeTeamId) {
      fetchDocuments(activeTeamId);
    } else {
      setDocuments([]);
    }
  }, [activeTeamId, fetchDocuments]);

  // Handle active team selection change
  const handleTeamChange = (value: string) => {
    setActiveTeamId(value);
    localStorage.setItem('active_team_id', value);
  };

  // Handle document upload
  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!activeTeamId) {
      setError('Please select an active team workspace first.');
      return;
    }

    const files = fileInputRef.current?.files;
    if (!files || files.length === 0) {
      setError('Please select a file to upload.');
      return;
    }

    const file = files[0];
    const validation = validateFile(file, 50 * 1024 * 1024); // 50MB
    if (!validation.valid) {
      setError(validation.error || 'Invalid file');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);

    try {
      const res = await apiFetch('/api/upload', {
        method: 'POST',
        headers: {
          'X-Active-Team-ID': activeTeamId,
        },
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setSuccess(`File "${file.name}" is now processing.`);
        
        // Add to active upload tasks
        const newUpload: UploadTask = {
          id: Math.random().toString(),
          filename: file.name,
          status: 'processing',
          taskId: data.task_id,
        };
        setUploads((prev) => [newUpload, ...prev]);

        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      } else {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
        setError(err.detail || 'Upload failed');
      }
    } catch {
      setError('Network error during file upload');
    } finally {
      setUploading(false);
    }
  };

  // Poll active tasks status
  useEffect(() => {
    const processingTasks = uploads.filter((u) => u.status === 'processing');
    if (processingTasks.length === 0) return;

    const interval = setInterval(async () => {
      let changed = false;
      const updatedUploads = await Promise.all(
        uploads.map(async (task) => {
          if (task.status !== 'processing') return task;

          try {
            const res = await apiFetch(`/api/upload/status/${task.taskId}`);
            if (res.ok) {
              const data = await res.json();
              const normStatus = normalizeUploadStatus(data.status);
              if (normStatus === 'completed' || normStatus === 'failed') {
                changed = true;
                return { ...task, status: normStatus };
              }
            }
          } catch {
            // Log or ignore transient network errors during poll
          }
          return task;
        })
      );

      if (changed) {
        setUploads(updatedUploads);
        // Refresh document list if any task finished
        if (activeTeamId) {
          fetchDocuments(activeTeamId);
        }
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [uploads, activeTeamId, fetchDocuments]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-1">
          <h2 id="docs-title" className="text-2xl font-bold tracking-tight text-foreground">
            Document Ingestion Console
          </h2>
          <p className="text-sm text-muted-foreground">
            Upload text, PDF, and DOCX files into Weaviate and Neo4j.
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Active Team:</span>
          {loadingTeams ? (
            <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
          ) : (
            <Select value={activeTeamId} onValueChange={(val) => handleTeamChange(val || '')}>
              <SelectTrigger id="team-select" className="w-[200px]">
                <SelectValue placeholder="Select team..." />
              </SelectTrigger>
              <SelectContent>
                {teams.map((t) => (
                  <SelectItem key={t.team_id} value={t.team_id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Upload Card */}
        <Card className="lg:col-span-1 border-border bg-card">
          <form onSubmit={handleUpload}>
            <CardHeader>
              <CardTitle className="text-lg">Ingest New File</CardTitle>
              <CardDescription>
                Files must not exceed size limits.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <AlertBanner type="error" message={error} />
              <AlertBanner type="success" message={success} />
              
              <div className="flex flex-col gap-2">
                <label htmlFor="file-input" className="text-sm font-medium">Select Document</label>
                <Input
                  id="file-input"
                  type="file"
                  ref={fileInputRef}
                  required
                  accept=".pdf,.docx,.txt,.md,.xlsx,.pptx"
                  className="bg-background border-border text-foreground placeholder:text-muted-foreground file:text-foreground cursor-pointer"
                />
              </div>
            </CardContent>
            <CardFooter>
              <Button
                id="upload-button"
                type="submit"
                disabled={uploading || !activeTeamId}
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90 font-medium flex gap-2 items-center justify-center"
              >
                {uploading ? (
                  <>
                    <Loader2Icon className="size-4 animate-spin" />
                    <span>Uploading...</span>
                  </>
                ) : (
                  <>
                    <UploadIcon className="size-4" />
                    <span>Upload Document</span>
                  </>
                )}
              </Button>
            </CardFooter>
          </form>
        </Card>

        {/* Polling Ingestions Card */}
        <Card className="lg:col-span-2 border-border bg-card">
          <CardHeader>
            <CardTitle className="text-lg">Active Ingestions</CardTitle>
            <CardDescription>
              Celery task execution status.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {uploads.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground gap-2">
                <FileTextIcon className="size-8 opacity-45" />
                <span className="text-sm">No uploads in the current session.</span>
              </div>
            ) : (
              <div className="overflow-x-auto border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Filename</TableHead>
                      <TableHead>Task ID</TableHead>
                      <TableHead className="w-[120px]">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {uploads.map((task) => (
                      <TableRow key={task.id}>
                        <TableCell className="font-medium truncate max-w-[200px]" title={task.filename}>
                          {task.filename}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {task.taskId}
                        </TableCell>
                        <TableCell>
                          {task.status === 'processing' && (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-500">
                              <Loader2Icon className="size-3 animate-spin" />
                              Processing
                            </span>
                          )}
                          {task.status === 'completed' && (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500">
                              <CheckCircle2Icon className="size-3" />
                              Completed
                            </span>
                          )}
                          {task.status === 'failed' && (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-destructive/10 text-destructive">
                              <XCircleIcon className="size-3" />
                              Failed
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Uploaded Documents Table */}
      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-lg">Ingested Documents</CardTitle>
          <CardDescription>
            Successfully processed files available for search and graph retrieval.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loadingDocs ? (
            <div className="flex justify-center p-8">
              <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground gap-2">
              <FileTextIcon className="size-8 opacity-45" />
              <span className="text-sm">No ingested documents found for this team.</span>
            </div>
          ) : (
            <div className="overflow-x-auto border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Filename</TableHead>
                    <TableHead>Document ID</TableHead>
                    <TableHead className="w-[200px]">Ingested At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <TableRow key={doc.parent_id}>
                      <TableCell className="font-medium">{doc.filename}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {doc.parent_id}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
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
    </div>
  );
}
