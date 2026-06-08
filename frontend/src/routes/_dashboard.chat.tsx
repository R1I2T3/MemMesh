import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { useState, useEffect, useRef, useCallback } from 'react';
import { apiFetch, API_BASE } from '../lib/api';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { clientSideInputCheck } from '../utils/safety';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  MessageSquareIcon,
  GitBranchIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  SendIcon,
  PlusIcon,
  XIcon,
  Loader2Icon,
  AlertTriangleIcon,
  UserIcon,
  BotIcon
} from 'lucide-react';
import {
  getLeafMessages,
  reconstructActivePath,
  findLatestLeaf,
  Message
} from '../utils/query';
import { CitationDrawer, Citation } from '../components/CitationDrawer';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/chat',
  component: ChatInterfaceConsole,
});

interface Team {
  team_id: string;
  name: string;
}

function ChatInterfaceConsole() {
  // Team Selection State
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeTeamId, setActiveTeamId] = useState<string>(() => {
    return localStorage.getItem('active_team_id') || '';
  });

  // Session Selection State
  const [sessions, setSessions] = useState<string[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('default-session');
  const [newSessionInput, setNewSessionInput] = useState<string>('');

  // Messages State
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [parentMsgId, setParentMsgId] = useState<string | null>(null);

  // Input Query State
  const [queryInput, setQueryInput] = useState<string>('');

  // UI / Loading / Error States
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sendingQuery, setSendingQuery] = useState(false);
  const [error, setError] = useState('');

  // Citation Drawer State
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const handleCitationClick = (citation: Citation) => {
    setSelectedCitation(citation);
    setIsDrawerOpen(true);
  };

  const renderMessageContent = (msg: Message) => {
    if (msg.role !== 'assistant' || !msg.citations || msg.citations.length === 0) {
      return <div className="whitespace-pre-wrap">{msg.content}</div>;
    }

    // Match citations like [1] or [Web 1]
    const regex = /(\[(?:Web\s+\d+|\d+)\])/gi;
    const parts = msg.content.split(regex);
    if (parts.length === 1) {
      return <div className="whitespace-pre-wrap">{msg.content}</div>;
    }

    const renderedParts: React.ReactNode[] = [];
    for (let i = 0; i < parts.length; i++) {
      if (i % 2 === 0) {
        // Normal text
        renderedParts.push(parts[i]);
      } else {
        // Citation tag (e.g., "[1]" or "[Web 1]")
        const tag = parts[i];
        const ref = tag.substring(1, tag.length - 1);
        let targetCitation: Citation | null = null;

        if (/^\d+$/.test(ref)) {
          // Numeric citation index (1-based)
          const idx = parseInt(ref, 10) - 1;
          if (msg.citations && idx >= 0 && idx < msg.citations.length) {
            targetCitation = msg.citations[idx];
          }
        } else {
          // Web citation index (e.g. "Web 1" or "Web 2")
          const match = ref.match(/Web\s+(\d+)/i);
          if (match) {
            const webIdx = parseInt(match[1], 10) - 1;
            const webCitations = msg.citations.filter((c: any) => c.type === 'web' || !!c.url);
            if (webIdx >= 0 && webIdx < webCitations.length) {
              targetCitation = webCitations[webIdx];
            }
          }
        }

        if (targetCitation) {
          renderedParts.push(
            <button
              key={i}
              onClick={() => handleCitationClick(targetCitation!)}
              className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-900/60 dark:hover:bg-indigo-900/50 transition-colors shadow-sm cursor-pointer align-baseline font-mono"
              title={`View source: ${targetCitation.source || targetCitation.url || 'Document'}`}
            >
              {tag}
            </button>
          );
        } else {
          renderedParts.push(tag);
        }
      }
    }

    return <div className="whitespace-pre-wrap">{renderedParts}</div>;
  };

  const chatEndRef = useRef<HTMLDivElement>(null);

  // 1. Fetch Teams
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
      } else {
        setError('Failed to load teams');
      }
    } catch {
      setError('Failed to load teams');
    } finally {
      setLoadingTeams(false);
    }
  }, [activeTeamId]);

  // 2. Fetch Sessions
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

  // 3. Fetch Messages for Session
  const fetchMessages = useCallback(async (sessionId: string) => {
    if (!sessionId) return;
    setLoadingMessages(true);
    setError('');
    try {
      const res = await apiFetch(`/api/chat/messages?session_id=${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
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

  // Initial loads
  useEffect(() => {
    fetchTeams();
    fetchSessions();
  }, [fetchTeams, fetchSessions]);

  // Reload messages when session changes
  useEffect(() => {
    fetchMessages(activeSessionId);
  }, [activeSessionId, fetchMessages]);

  // Auto-scroll to bottom of chat when path changes or loading status changes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeMessageId, sendingQuery]);

  // Re-establish activeMessageId when messages list changes
  useEffect(() => {
    if (messages.length > 0) {
      const exists = messages.some((m) => m.message_id === activeMessageId);
      if (!activeMessageId || !exists) {
        const leaves = getLeafMessages(messages);
        if (leaves.length > 0) {
          // Default to the latest leaf in chronological order (last item)
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

  // Active path reconstruction
  const activePath = reconstructActivePath(messages, activeMessageId);

  // Filter root level messages to determine if there are root-level branches
  const roots = messages.filter((m) => m.parent_message_id === null);

  // Handle Send Query
  const handleSendQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim() || sendingQuery) return;

    setError('');
    const currentQuery = queryInput;
    const currentParentId = parentMsgId;

    // Client-side SQL injection validation
    if (!clientSideInputCheck(currentQuery)) {
      setError('Input query failed client-side security checks (SQL injection pattern detected).');
      return;
    }

    setSendingQuery(true);
    setQueryInput('');

    const queryParams = new URLSearchParams({
      q: currentQuery,
      session_id: activeSessionId
    });
    if (activeTeamId) {
      queryParams.append('team_id', activeTeamId);
    }
    if (currentParentId) {
      queryParams.append('parent_msg_id', currentParentId);
    }

    const token = localStorage.getItem('token');
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const abortController = new AbortController();

    let assistantId = '';
    let userId = '';
    let currentResponseText = '';

    try {
      await fetchEventSource(`${API_BASE}/api/query/stream?${queryParams.toString()}`, {
        method: 'GET',
        headers,
        signal: abortController.signal,
        async onopen(response) {
          if (response.ok) {
            return;
          }
          let errMsg = `Server returned status ${response.status}`;
          try {
            const errData = await response.json();
            errMsg = errData.detail || errMsg;
          } catch {}
          throw new Error(errMsg);
        },
        onmessage(ev) {
          if (ev.data === '[DONE]') {
            setSendingQuery(false);
            fetchMessages(activeSessionId);
            fetchSessions();
            setParentMsgId(null);
            abortController.abort(); // clean up the stream connection
            return;
          }

          try {
            const data = JSON.parse(ev.data);
            if (data.message_id && data.user_message_id) {
              assistantId = data.message_id;
              userId = data.user_message_id;

              const newUserMsg: Message = {
                message_id: userId,
                session_id: activeSessionId,
                parent_message_id: currentParentId,
                role: 'user',
                content: currentQuery,
                created_at: new Date().toISOString()
              };

              const newAssistantMsg: Message = {
                message_id: assistantId,
                session_id: activeSessionId,
                parent_message_id: userId,
                role: 'assistant',
                content: '',
                created_at: new Date().toISOString(),
                citations: data.citations || []
              };

              setMessages((prev) => [...prev, newUserMsg, newAssistantMsg]);
              setActiveMessageId(assistantId);
            } else if (data.token) {
              currentResponseText += data.token;
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.message_id === assistantId
                    ? { ...msg, content: currentResponseText }
                    : msg
                )
              );
            }
          } catch (err) {
            console.error('Error parsing SSE event:', err);
          }
        },
        onerror(err) {
          setError(err.message || 'Stream connection error');
          setSendingQuery(false);
          setQueryInput(currentQuery); // restore input
          abortController.abort();
          throw err; // prevent automatic retry by fetchEventSource
        }
      });
    } catch (err: any) {
      setError(err.message || 'Network error sending query');
      setQueryInput(currentQuery);
      setSendingQuery(false);
    }
  };

  // Switch Active Team
  const handleTeamChange = (teamId: string) => {
    setActiveTeamId(teamId);
    localStorage.setItem('active_team_id', teamId);
  };

  // Add / Switch Session
  const handleAddSession = () => {
    if (!newSessionInput.trim()) return;
    const sId = newSessionInput.trim();
    if (!sessions.includes(sId)) {
      setSessions((prev) => [...prev, sId]);
    }
    setActiveSessionId(sId);
    setNewSessionInput('');
    setMessages([]);
    setActiveMessageId(null);
    setParentMsgId(null);
  };

  return (
    <div className="flex flex-col md:flex-row gap-6 p-6 h-[calc(100vh-80px)] overflow-hidden">
      {/* Sidebar Control Panel */}
      <Card className="w-full md:w-80 flex-shrink-0 flex flex-col max-h-full">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg flex items-center gap-2">
            <MessageSquareIcon className="size-5 text-indigo-500" />
            Chat Workspace
          </CardTitle>
          <CardDescription>Configure team context and sessions</CardDescription>
        </CardHeader>
        <CardContent className="flex-grow flex flex-col gap-4 overflow-y-auto">
          {/* Team Selection */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Active Team Context
            </label>
            {loadingTeams ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <Select value={activeTeamId} onValueChange={(val) => handleTeamChange(val || '')}>
                <SelectTrigger>
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

          {/* Session Selection */}
          <div className="flex flex-col gap-2 flex-grow">
            <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Chat Session
            </label>
            {loadingSessions ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <Select value={activeSessionId} onValueChange={(val) => {
                setActiveSessionId(val || 'default-session');
                setParentMsgId(null);
                setActiveMessageId(null);
              }}>
                <SelectTrigger>
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

            <div className="flex gap-2 mt-2">
              <Input
                id="new-session-input"
                placeholder="New session ID..."
                value={newSessionInput}
                onChange={(e) => setNewSessionInput(e.target.value)}
                className="flex-grow"
              />
              <Button id="add-session-btn" size="icon" onClick={handleAddSession} variant="secondary">
                <PlusIcon className="size-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Chat Area */}
      <Card className="flex-grow flex flex-col h-full relative overflow-hidden bg-background">
        {/* Header */}
        <div className="p-4 border-b flex flex-col md:flex-row md:items-center justify-between gap-4 bg-muted/20">
          <div>
            <h2 id="chat-title" className="text-lg font-bold tracking-tight">
              Chat Interface Console
            </h2>
            <p className="text-xs text-muted-foreground">
              Session: <span className="font-mono text-indigo-500">{activeSessionId}</span>
            </p>
          </div>
          {/* Root-Level Branch Switcher */}
          {roots.length > 1 && (
            <div className="flex items-center gap-2 border bg-background px-3 py-1 rounded-md text-xs">
              <span className="font-medium text-muted-foreground">Thread Roots:</span>
              <span className="font-mono">
                {roots.findIndex((r) => activePath.some((ap) => ap.message_id === r.message_id)) + 1} of {roots.length}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-6"
                  onClick={() => {
                    const activeRootIndex = roots.findIndex((r) => activePath.some((ap) => ap.message_id === r.message_id));
                    const prevIndex = (activeRootIndex - 1 + roots.length) % roots.length;
                    const newLeafId = findLatestLeaf(messages, roots[prevIndex].message_id);
                    setActiveMessageId(newLeafId);
                  }}
                >
                  <ChevronLeftIcon className="size-4" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-6"
                  onClick={() => {
                    const activeRootIndex = roots.findIndex((r) => activePath.some((ap) => ap.message_id === r.message_id));
                    const nextIndex = (activeRootIndex + 1) % roots.length;
                    const newLeafId = findLatestLeaf(messages, roots[nextIndex].message_id);
                    setActiveMessageId(newLeafId);
                  }}
                >
                  <ChevronRightIcon className="size-4" />
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Error Alert */}
        {error && (
          <div className="bg-destructive/10 border-b border-destructive/20 p-3 text-destructive text-xs flex items-center gap-2">
            <AlertTriangleIcon className="size-4 shrink-0" />
            <span>{error}</span>
            <Button size="icon" variant="ghost" className="size-4 ml-auto hover:bg-transparent" onClick={() => setError('')}>
              <XIcon className="size-3" />
            </Button>
          </div>
        )}

        {/* Message Feed Area */}
        <div className="flex-grow overflow-y-auto p-4 flex flex-col gap-4">
          {loadingMessages ? (
            <div className="flex flex-col gap-4">
              <Skeleton className="h-16 w-3/4 rounded-lg self-start" />
              <Skeleton className="h-16 w-3/4 rounded-lg self-end" />
              <Skeleton className="h-20 w-3/4 rounded-lg self-start" />
            </div>
          ) : activePath.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-8">
              <div className="bg-indigo-50 dark:bg-indigo-950/30 p-4 rounded-full mb-4">
                <MessageSquareIcon className="size-8 text-indigo-500" />
              </div>
              <h3 className="font-semibold text-slate-800 dark:text-slate-200">No message history</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-sm">
                Send your first message to initialize the LangGraph agent chain in this session.
              </p>
            </div>
          ) : (
            activePath.map((msg) => {
              const isUser = msg.role === 'user';
              // Find children of this message in the FULL list
              const children = messages.filter((m) => m.parent_message_id === msg.message_id);
              // Find which child is in the current active path
              const nextMsgInPath = activePath[activePath.indexOf(msg) + 1];
              const activeChildId = nextMsgInPath ? nextMsgInPath.message_id : null;
              const activeChildIndex = children.findIndex((c) => c.message_id === activeChildId);

              return (
                <div key={msg.message_id} className="flex flex-col gap-2 group">
                  <div className={`flex gap-3 max-w-[85%] ${isUser ? 'self-end flex-row-reverse' : 'self-start'}`}>
                    {/* Avatar */}
                    <div className={`size-8 rounded-full flex items-center justify-center flex-shrink-0 border ${
                      isUser ? 'bg-indigo-600 text-white border-indigo-500' : 'bg-muted border-slate-200 dark:border-slate-800'
                    }`}>
                      {isUser ? <UserIcon className="size-4" /> : <BotIcon className="size-4" />}
                    </div>

                    {/* Speech bubble */}
                    <div className="flex flex-col gap-1">
                      <div className={`p-3.5 rounded-2xl relative shadow-sm border text-sm leading-relaxed transition-all duration-200 ${
                        isUser
                          ? 'bg-indigo-600 border-indigo-500 text-white rounded-tr-none'
                          : 'bg-card border-slate-200 dark:border-slate-800 text-foreground rounded-tl-none'
                      }`}>
                        {renderMessageContent(msg)}

                        {/* Hover Action Button for Branching */}
                        <div className={`absolute top-1/2 -translate-y-1/2 flex gap-1 transition-opacity opacity-0 group-hover:opacity-100 ${
                          isUser ? 'right-full mr-2' : 'left-full ml-2'
                        }`}>
                          <Button
                            size="sm"
                            variant="secondary"
                            className="h-7 px-2.5 text-xs flex items-center gap-1 shadow-sm border border-slate-200 dark:border-slate-800 bg-background hover:bg-muted"
                            onClick={() => setParentMsgId(msg.message_id)}
                          >
                            <GitBranchIcon className="size-3 text-indigo-500" />
                            <span>Branch</span>
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Sub-Branch Switcher */}
                  {children.length > 1 && (
                    <div className={`flex items-center gap-2 text-[11px] px-11 text-muted-foreground ${isUser ? 'justify-end' : 'justify-start'}`}>
                      <div className="flex items-center gap-1 border rounded bg-background px-2 py-0.5 shadow-sm">
                        <span className="font-semibold text-slate-700 dark:text-slate-300">Branch:</span>
                        <span>
                          {activeChildIndex !== -1 ? activeChildIndex + 1 : 1} of {children.length}
                        </span>
                        <div className="flex items-center gap-0.5 ml-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-4"
                            onClick={() => {
                              const currIdx = activeChildIndex !== -1 ? activeChildIndex : 0;
                              const prevIdx = (currIdx - 1 + children.length) % children.length;
                              const newChild = children[prevIdx];
                              const newLeafId = findLatestLeaf(messages, newChild.message_id);
                              setActiveMessageId(newLeafId);
                            }}
                          >
                            <ChevronLeftIcon className="size-3" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-4"
                            onClick={() => {
                              const currIdx = activeChildIndex !== -1 ? activeChildIndex : 0;
                              const nextIdx = (currIdx + 1) % children.length;
                              const newChild = children[nextIdx];
                              const newLeafId = findLatestLeaf(messages, newChild.message_id);
                              setActiveMessageId(newLeafId);
                            }}
                          >
                            <ChevronRightIcon className="size-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}

          {/* Query Pending/Typing Skeleton */}
          {sendingQuery && (
            <div className="flex gap-3 max-w-[85%] self-start">
              <div className="size-8 rounded-full flex items-center justify-center flex-shrink-0 bg-muted border border-slate-200 dark:border-slate-800">
                <BotIcon className="size-4 text-muted-foreground animate-pulse" />
              </div>
              <div className="flex flex-col gap-1 w-64">
                <Skeleton className="h-10 w-full rounded-2xl rounded-tl-none" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input & Form Panel */}
        <div className="p-4 border-t bg-muted/10 flex flex-col gap-2">
          {/* Active branch indicators */}
          {parentMsgId && (
            <div className="flex items-center justify-between bg-indigo-500/10 border border-indigo-500/20 text-indigo-500 px-3 py-1.5 rounded-lg text-xs">
              <div className="flex items-center gap-1.5">
                <GitBranchIcon className="size-3.5" />
                <span>
                  Branching thread from message:{' '}
                  <span className="font-mono font-bold bg-indigo-500/20 px-1.5 py-0.5 rounded">
                    {parentMsgId.substring(0, 8)}...
                  </span>
                </span>
              </div>
              <Button
                size="icon"
                variant="ghost"
                className="size-5 hover:bg-indigo-500/20 text-indigo-500"
                onClick={() => setParentMsgId(null)}
              >
                <XIcon className="size-3" />
              </Button>
            </div>
          )}

          <form onSubmit={handleSendQuery} className="flex gap-2">
            <Input
              placeholder="Ask anything, agent orchestrator will route your query..."
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              disabled={sendingQuery}
              className="flex-grow bg-background"
            />
            <Button type="submit" disabled={sendingQuery || !queryInput.trim()} className="px-4 gap-1.5">
              {sendingQuery ? <Loader2Icon className="size-4 animate-spin" /> : <SendIcon className="size-4" />}
              <span>Send</span>
            </Button>
          </form>
        </div>
      </Card>
      <CitationDrawer
        isOpen={isDrawerOpen}
        onOpenChange={setIsDrawerOpen}
        citation={selectedCitation}
      />
    </div>
  );
}
