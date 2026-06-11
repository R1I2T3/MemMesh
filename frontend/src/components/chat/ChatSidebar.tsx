import { useState } from 'react';
import { Settings2Icon, PlusIcon } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { Team } from '@/types/api';

interface ChatSidebarProps {
  teams: Team[];
  activeTeamId: string;
  sessions: string[];
  activeSessionId: string;
  loadingTeams: boolean;
  loadingSessions: boolean;
  onTeamChange: (teamId: string) => void;
  onSessionChange: (sessionId: string) => void;
  onAddSession: (sessionId: string) => void;
}

export function ChatSidebar({
  teams,
  activeTeamId,
  sessions,
  activeSessionId,
  loadingTeams,
  loadingSessions,
  onTeamChange,
  onSessionChange,
  onAddSession,
}: ChatSidebarProps) {
  const [newSessionInput, setNewSessionInput] = useState('');

  const handleAddSession = () => {
    if (!newSessionInput.trim()) return;
    onAddSession(newSessionInput.trim());
    setNewSessionInput('');
  };

  return (
    <Card className="w-full md:w-72 flex-shrink-0 flex flex-col max-h-full border-border/80 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2 font-semibold">
          <div className="flex items-center justify-center rounded-lg bg-primary/10 p-1.5 text-primary">
            <Settings2Icon className="size-4" />
          </div>
          Chat Workspace
        </CardTitle>
        <CardDescription className="text-[11px]">Configure team and session</CardDescription>
      </CardHeader>
      <CardContent className="flex-grow flex flex-col gap-4 overflow-y-auto">
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-[0.1em]">
            Active Team
          </label>
          {loadingTeams ? (
            <Skeleton className="h-9 w-full rounded-lg" />
          ) : (
            <Select value={activeTeamId} onValueChange={(val) => onTeamChange(val || '')}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="Select team" />
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

        <div className="flex flex-col gap-1.5 flex-grow">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-[0.1em]">
            Chat Session
          </label>
          {loadingSessions ? (
            <Skeleton className="h-9 w-full rounded-lg" />
          ) : (
            <Select value={activeSessionId} onValueChange={(val) => onSessionChange(val || 'default-session')}>
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="Select session" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default-session">default-session</SelectItem>
                {sessions
                  .filter((s) => s !== 'default-session')
                  .map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          )}

          <div className="flex gap-2 mt-1">
            <Input
              id="new-session-input"
              placeholder="New session ID..."
              value={newSessionInput}
              onChange={(e) => setNewSessionInput(e.target.value)}
              className="flex-grow h-9 text-xs"
            />
            <Button id="add-session-btn" size="icon-sm" onClick={handleAddSession} variant="secondary">
              <PlusIcon className="size-[14px]" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
