import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { useState, useEffect, useRef, useCallback } from 'react';
import { apiFetch } from '../lib/api';
import { chatSearchSchema } from './search.schemas';
import { useChatStream } from '@/hooks/useChatStream';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { BranchSwitcher } from '@/components/chat/BranchSwitcher';
import { StreamingSkeleton } from '@/components/chat/StreamingSkeleton';
import { CitationDrawer, type Citation } from '@/components/CitationDrawer';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangleIcon, XIcon, MessageSquareIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  getLeafMessages,
  reconstructActivePath,
  findLatestLeaf,
} from '../utils/query';
import type { Message, Team } from '@/types/api';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/chat',
  validateSearch: chatSearchSchema,
  component: ChatInterfaceConsole,
});

function ChatInterfaceConsole() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeTeamId, setActiveTeamId] = useState<string>(() => {
    return localStorage.getItem('active_team_id') || '';
  });

  const [sessions, setSessions] = useState<string[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('default-session');
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [parentMsgId, setParentMsgId] = useState<string | null>(null);

  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState('');

  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const { sendQuery, sendingQuery, streamError } = useChatStream();
  const chatEndRef = useRef<HTMLDivElement>(null);

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

  const fetchSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const res = await apiFetch('/api/chat/sessions');
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch {
      setError('Failed to load chat sessions');
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  const fetchMessages = useCallback(async (sessionId: string) => {
    if (!sessionId) return;
    setLoadingMessages(true);
    setError('');
    try {
      const res = await apiFetch(`/api/chat/messages?session_id=${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        const msgs = data.messages || [];
        setMessages(msgs);
        const leaves = getLeafMessages(msgs);
        if (leaves.length > 0) {
          setActiveMessageId(leaves[leaves.length - 1].message_id);
        } else {
          setActiveMessageId(null);
        }
      } else {
        setMessages([]);
        setError('Failed to load messages');
      }
    } catch {
      setMessages([]);
      setError('Failed to load messages');
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    fetchTeams();
    fetchSessions();
  }, [fetchTeams, fetchSessions]);

  useEffect(() => {
    fetchMessages(activeSessionId);
  }, [activeSessionId, fetchMessages]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeMessageId, sendingQuery]);

  useEffect(() => {
    if (messages.length > 0) {
      const exists = messages.some((m) => m.message_id === activeMessageId);
      if (!activeMessageId || !exists) {
        const leaves = getLeafMessages(messages);
        if (leaves.length > 0) {
          const latestLeaf = leaves[leaves.length - 1];
          setActiveMessageId(latestLeaf.message_id);
        } else {
          setActiveMessageId(null);
        }
      }
    } else {
      setActiveMessageId(null);
    }
  }, [messages, activeMessageId]);

  const activePath = reconstructActivePath(messages, activeMessageId);
  const roots = messages.filter((m) => m.parent_message_id === null);

  const handleSendQuery = async (query: string, currentParentId: string | null) => {
    await sendQuery({
      query,
      sessionId: activeSessionId,
      parentMsgId: currentParentId,
      onUpdate: (update) => {
        switch (update.type) {
          case 'pending':
            setMessages((prev) => [...prev, update.userMsg, update.assistantMsg]);
            setActiveMessageId(update.assistantMsg.message_id);
            break;
          case 'chunk':
            setMessages((prev) =>
              prev.map((msg) =>
                msg.message_id.startsWith('pending-')
                  ? { ...msg, content: msg.content + update.text }
                  : msg,
              ),
            );
            break;
          case 'resolved':
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.message_id === update.userId) return { ...msg, message_id: update.userId };
                if (msg.message_id.startsWith('pending-')) return { ...msg, message_id: update.assistantId };
                return msg;
              }),
            );
            break;
          case 'done':
            if (update.citations.length > 0) {
              setMessages((prev) =>
                prev.map((msg) => {
                  const msgId = msg.message_id.startsWith('pending-') ? 'assistant' : msg.message_id;
                  return msg.role === 'assistant' && (msg.message_id === activeMessageId || msgId === 'assistant')
                    ? { ...msg, citations: update.citations }
                    : msg;
                }),
              );
            }
            fetchMessages(activeSessionId);
            fetchSessions();
            setParentMsgId(null);
            break;
          case 'error':
            setError(update.detail);
            break;
        }
      },
    });
  };

  const handleExport = async (format: 'md' | 'json') => {
    try {
      const res = await apiFetch(`/api/chat/sessions/${activeSessionId}/export?format=${format}`);
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || 'Export failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${activeSessionId}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  const handleFeedback = async (msgId: string, rating: number) => {
    const msg = messages.find((m) => m.message_id === msgId);
    if (!msg) return;

    const parentMsg = messages.find((m) => m.message_id === msg.parent_message_id);
    const query = parentMsg ? parentMsg.content : 'Unknown Query';
    const response = msg.content;
    const traceId = `trace-${Date.now()}`;

    try {
      const res = await apiFetch('/api/feedback', {
        method: 'POST',
        body: JSON.stringify({ query, response, rating, trace_id: traceId }),
      });
      if (res.ok) {
        setRatings((prev) => ({ ...prev, [msgId]: rating }));
      } else {
        setError('Failed to submit feedback');
      }
    } catch {
      setError('Failed to submit feedback due to network error');
    }
  };

  const handleTeamChange = (teamId: string) => {
    setActiveTeamId(teamId);
    localStorage.setItem('active_team_id', teamId);
  };

  const handleAddSession = (sessionId: string) => {
    if (!sessions.includes(sessionId)) {
      setSessions((prev) => [...prev, sessionId]);
    }
    setActiveSessionId(sessionId);
    setMessages([]);
    setActiveMessageId(null);
    setParentMsgId(null);
  };

  const handleSessionChange = (sessionId: string) => {
    setActiveSessionId(sessionId);
    setParentMsgId(null);
    setActiveMessageId(null);
  };

  const combinedError = error || streamError;

  return (
    <div className="flex flex-col md:flex-row gap-5 h-[calc(100vh-80px)] overflow-hidden max-w-6xl mx-auto">
      <ChatSidebar
        teams={teams}
        activeTeamId={activeTeamId}
        sessions={sessions}
        activeSessionId={activeSessionId}
        loadingTeams={loadingTeams}
        loadingSessions={loadingSessions}
        onTeamChange={handleTeamChange}
        onSessionChange={handleSessionChange}
        onAddSession={handleAddSession}
      />

      <Card className="flex-grow flex flex-col h-full relative overflow-hidden bg-card border-border/80 shadow-sm">
        <ChatHeader
          activeSessionId={activeSessionId}
          threadPosition={
            roots.length > 0
              ? `${roots.findIndex((r) => activePath.some((ap) => ap.message_id === r.message_id)) + 1}/${roots.length}`
              : ''
          }
          hasMultipleThreads={roots.length > 1}
          onPrevThread={() => {
            const activeRootIndex = roots.findIndex((r) =>
              activePath.some((ap) => ap.message_id === r.message_id),
            );
            const prevIndex = (activeRootIndex - 1 + roots.length) % roots.length;
            const newLeafId = findLatestLeaf(messages, roots[prevIndex].message_id);
            setActiveMessageId(newLeafId);
          }}
          onNextThread={() => {
            const activeRootIndex = roots.findIndex((r) =>
              activePath.some((ap) => ap.message_id === r.message_id),
            );
            const nextIndex = (activeRootIndex + 1) % roots.length;
            const newLeafId = findLatestLeaf(messages, roots[nextIndex].message_id);
            setActiveMessageId(newLeafId);
          }}
          onExport={handleExport}
        />

        {combinedError && (
          <div className="bg-destructive/8 border-b border-destructive/15 px-4 py-2.5 text-destructive text-xs flex items-center gap-2">
            <AlertTriangleIcon className="size-3.5 shrink-0" />
            <span className="flex-1">{combinedError}</span>
            <Button size="icon-xs" variant="ghost" className="text-destructive/60 hover:text-destructive" onClick={() => setError('')}>
              <XIcon className="size-3" />
            </Button>
          </div>
        )}

        <div className="flex-grow overflow-y-auto px-4 md:px-8 py-5">
          <div className="max-w-3xl mx-auto flex flex-col gap-5">
            {loadingMessages ? (
              <div className="flex flex-col gap-5">
                <div className="flex gap-3 self-start max-w-[75%]">
                  <Skeleton className="size-8 rounded-full shrink-0" />
                  <div className="flex flex-col gap-2 flex-1">
                    <Skeleton className="h-12 w-64 rounded-2xl rounded-tl-none" />
                  </div>
                </div>
                <div className="flex gap-3 self-end max-w-[75%]">
                  <Skeleton className="size-8 rounded-full shrink-0" />
                  <div className="flex flex-col gap-2">
                    <Skeleton className="h-10 w-48 rounded-2xl rounded-tr-none" />
                  </div>
                </div>
                <div className="flex gap-3 self-start max-w-[75%]">
                  <Skeleton className="size-8 rounded-full shrink-0" />
                  <div className="flex flex-col gap-2 flex-1">
                    <Skeleton className="h-20 w-72 rounded-2xl rounded-tl-none" />
                  </div>
                </div>
              </div>
            ) : activePath.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-16">
                <div className="bg-gradient-to-br from-primary/10 to-primary/5 p-4 rounded-2xl mb-5 ring-1 ring-primary/10">
                  <MessageSquareIcon className="size-8 text-primary/60" />
                </div>
                <h3 className="font-semibold text-foreground text-sm">No message history</h3>
                <p className="text-xs text-muted-foreground mt-1.5 max-w-xs leading-relaxed">
                  Send your first message to initialize the LangGraph agent chain in this session.
                </p>
              </div>
            ) : (
              activePath.map((msg) => {
                const isUser = msg.role === 'user';
                const children = messages.filter((m) => m.parent_message_id === msg.message_id);
                const nextMsgInPath = activePath[activePath.indexOf(msg) + 1];
                const activeChildId = nextMsgInPath ? nextMsgInPath.message_id : null;
                const activeChildIndex = children.findIndex((c) => c.message_id === activeChildId);

                return (
                  <ChatMessage
                    key={msg.message_id}
                    message={msg}
                    onBranch={setParentMsgId}
                    onFeedback={handleFeedback}
                    onCitationClick={(citation) => {
                      setSelectedCitation(citation);
                      setIsDrawerOpen(true);
                    }}
                    ratings={ratings}
                  >
                    {children.length > 1 && (
                      <BranchSwitcher
                        currentIndex={activeChildIndex !== -1 ? activeChildIndex : 0}
                        totalBranches={children.length}
                        isUser={isUser}
                        onPrev={() => {
                          const currIdx = activeChildIndex !== -1 ? activeChildIndex : 0;
                          const prevIdx = (currIdx - 1 + children.length) % children.length;
                          const newLeafId = findLatestLeaf(messages, children[prevIdx].message_id);
                          setActiveMessageId(newLeafId);
                        }}
                        onNext={() => {
                          const currIdx = activeChildIndex !== -1 ? activeChildIndex : 0;
                          const nextIdx = (currIdx + 1) % children.length;
                          const newLeafId = findLatestLeaf(messages, children[nextIdx].message_id);
                          setActiveMessageId(newLeafId);
                        }}
                      />
                    )}
                  </ChatMessage>
                );
              })
            )}

            {sendingQuery && <StreamingSkeleton />}
            <div ref={chatEndRef} />
          </div>
        </div>

        <ChatInput
          onSend={handleSendQuery}
          sendingQuery={sendingQuery}
          parentMsgId={parentMsgId}
          onCancelBranch={() => setParentMsgId(null)}
        />
      </Card>

      <CitationDrawer
        isOpen={isDrawerOpen}
        onOpenChange={setIsDrawerOpen}
        citation={selectedCitation}
      />
    </div>
  );
}
