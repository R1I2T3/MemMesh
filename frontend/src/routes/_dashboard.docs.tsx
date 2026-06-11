import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../lib/api';
import { UploadZone } from '@/components/docs/UploadZone';
import { UploadTaskTable } from '@/components/docs/UploadTaskTable';
import { DocumentTable } from '@/components/docs/DocumentTable';
import { SystemHardening } from '@/components/docs/SystemHardening';
import { EvalMetricsCard } from '@/components/docs/EvalMetricsCard';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2Icon } from 'lucide-react';
import { validateFile, normalizeUploadStatus } from '../utils/upload';
import { getStoredAuth } from '../utils/auth';
import type { Team, DocumentItem, UploadTask } from '@/types/api';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/docs',
  component: DocumentIngestionConsole,
});

function DocumentIngestionConsole() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeTeamId, setActiveTeamId] = useState<string>(() => {
    return localStorage.getItem('active_team_id') || '';
  });
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [uploads, setUploads] = useState<UploadTask[]>([]);

  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [evalResults, setEvalResults] = useState<any[] | null>(null);
  const [runningEval, setRunningEval] = useState(false);
  const [evalError, setEvalError] = useState('');

  const [decayTaskId, setDecayTaskId] = useState('');
  const [decayStatus, setDecayStatus] = useState('');
  const [decayLoading, setDecayLoading] = useState(false);
  const [decayResult, setDecayResult] = useState<any>(null);

  const [driftTaskId, setDriftTaskId] = useState('');
  const [driftStatus, setDriftStatus] = useState('');
  const [driftLoading, setDriftLoading] = useState(false);
  const [driftResult, setDriftResult] = useState<any>(null);

  const [hardeningError, setHardeningError] = useState('');

  const auth = getStoredAuth();
  const isSuperAdmin = auth?.role === 'superadmin';

  const fetchTeams = useCallback(async () => {
    setLoadingTeams(true);
    try {
      const res = await apiFetch('/api/teams');
      if (res.ok) {
        const data = await res.json();
        const teamsList: Team[] = data.teams || [];
        setTeams(teamsList);
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

  const fetchDocuments = useCallback(async (teamId: string) => {
    if (!teamId) return;
    setLoadingDocs(true);
    try {
      const res = await apiFetch('/api/documents', {
        headers: { 'X-Active-Team-ID': teamId },
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

  useEffect(() => {
    fetchTeams();
  }, [fetchTeams]);

  useEffect(() => {
    if (activeTeamId) {
      fetchDocuments(activeTeamId);
    } else {
      setDocuments([]);
    }
  }, [activeTeamId, fetchDocuments]);

  const handleTeamChange = (value: string) => {
    setActiveTeamId(value);
    localStorage.setItem('active_team_id', value);
  };

  const handleUpload = async (file: File) => {
    if (!activeTeamId) {
      setError('Please select an active team workspace first.');
      return;
    }

    const validation = validateFile(file, 50 * 1024 * 1024);
    if (!validation.valid) {
      setError(validation.error || 'Invalid file');
      return;
    }

    setError('');
    setSuccess('');
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await apiFetch('/api/upload', {
        method: 'POST',
        headers: { 'X-Active-Team-ID': activeTeamId },
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setSuccess(`File "${file.name}" is now processing.`);

        const newUpload: UploadTask = {
          id: Math.random().toString(),
          filename: file.name,
          status: 'processing',
          taskId: data.task_id,
        };
        setUploads((prev) => [newUpload, ...prev]);
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
          } catch {}
          return task;
        }),
      );

      if (changed) {
        setUploads(updatedUploads);
        if (activeTeamId) {
          fetchDocuments(activeTeamId);
        }
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [uploads, activeTeamId, fetchDocuments]);

  const runDecay = async () => {
    setDecayLoading(true);
    setDecayTaskId('');
    setDecayStatus('PENDING');
    setDecayResult(null);
    setHardeningError('');
    try {
      const res = await apiFetch('/api/decay/trigger', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setDecayTaskId(data.task_id);
        setDecayStatus('TRIGGERED');
      } else {
        const err = await res.json().catch(() => ({ detail: 'Failed to trigger decay' }));
        setHardeningError(err.detail || 'Failed to trigger decay');
        setDecayStatus('FAILED');
      }
    } catch {
      setHardeningError('Network error during memory decay trigger');
      setDecayStatus('FAILED');
    } finally {
      setDecayLoading(false);
    }
  };

  const runDrift = async () => {
    setDriftLoading(true);
    setDriftTaskId('');
    setDriftStatus('PENDING');
    setDriftResult(null);
    setHardeningError('');
    try {
      const res = await apiFetch('/api/drift/trigger', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setDriftTaskId(data.task_id);
        setDriftStatus('TRIGGERED');
      } else {
        const err = await res.json().catch(() => ({ detail: 'Failed to trigger drift' }));
        setHardeningError(err.detail || 'Failed to trigger drift');
        setDriftStatus('FAILED');
      }
    } catch {
      setHardeningError('Network error during drift detection trigger');
      setDriftStatus('FAILED');
    } finally {
      setDriftLoading(false);
    }
  };

  useEffect(() => {
    if (!decayTaskId) return;
    const interval = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/decay/status/${decayTaskId}`);
        if (res.ok) {
          const data = await res.json();
          setDecayStatus(data.status);
          if (data.status === 'SUCCESS' || data.status === 'FAILURE') {
            setDecayResult(data.result);
            clearInterval(interval);
          }
        }
      } catch {}
    }, 1500);
    return () => clearInterval(interval);
  }, [decayTaskId]);

  useEffect(() => {
    if (!driftTaskId) return;
    const interval = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/decay/status/${driftTaskId}`);
        if (res.ok) {
          const data = await res.json();
          setDriftStatus(data.status);
          if (data.status === 'SUCCESS' || data.status === 'FAILURE') {
            setDriftResult(data.result);
            clearInterval(interval);
          }
        }
      } catch {}
    }, 1500);
    return () => clearInterval(interval);
  }, [driftTaskId]);

  const runEvaluation = async () => {
    setRunningEval(true);
    setEvalResults(null);
    setEvalError('');
    try {
      const res = await apiFetch('/api/eval', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setEvalResults(data);
      } else {
        const err = await res.json().catch(() => ({ detail: 'Evaluation failed' }));
        setEvalError(err.detail || 'Evaluation failed');
      }
    } catch {
      setEvalError('Network error during evaluation');
    } finally {
      setRunningEval(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-0.5">
          <h2 id="docs-title" className="text-xl font-bold tracking-tight text-foreground">
            Document Ingestion
          </h2>
          <p className="text-xs text-muted-foreground">
            Upload text, PDF, and DOCX files into Weaviate and Neo4j.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">Team:</span>
          {loadingTeams ? (
            <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
          ) : (
            <Select value={activeTeamId} onValueChange={(val) => handleTeamChange(val || '')}>
              <SelectTrigger id="team-select" className="w-[180px] h-8 text-xs">
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <UploadZone
          onUpload={handleUpload}
          uploading={uploading}
          error={error}
          success={success}
          disabled={!activeTeamId}
        />
        <UploadTaskTable uploads={uploads} />
      </div>

      {isSuperAdmin && (
        <EvalMetricsCard
          results={evalResults}
          running={runningEval}
          error={evalError}
          onRun={runEvaluation}
        />
      )}

      {isSuperAdmin && (
        <SystemHardening
          decay={{
            taskId: decayTaskId,
            status: decayStatus,
            result: decayResult,
            loading: decayLoading,
          }}
          drift={{
            taskId: driftTaskId,
            status: driftStatus,
            result: driftResult,
            loading: driftLoading,
          }}
          error={hardeningError}
          onTriggerDecay={runDecay}
          onTriggerDrift={runDrift}
        />
      )}

      <DocumentTable documents={documents} loading={loadingDocs} />
    </div>
  );
}
