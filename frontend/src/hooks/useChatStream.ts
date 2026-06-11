import { useState, useCallback, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { API_BASE, authHeaders } from '@/lib/api';
import { clientSideInputCheck } from '@/utils/safety';
import type { Message, Citation } from '@/types/api';

export type StreamUpdate =
  | { type: 'pending'; userMsg: Message; assistantMsg: Message }
  | { type: 'chunk'; text: string }
  | { type: 'citation'; data: Citation }
  | { type: 'resolved'; userId: string; assistantId: string }
  | { type: 'done'; citations: Citation[] }
  | { type: 'error'; detail: string };

interface SendQueryParams {
  query: string;
  sessionId: string;
  parentMsgId: string | null;
  onUpdate: (update: StreamUpdate) => void;
}

export function useChatStream() {
  const [sendingQuery, setSendingQuery] = useState(false);
  const [streamError, setStreamError] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  const sendQuery = useCallback(async ({ query, sessionId, parentMsgId, onUpdate }: SendQueryParams) => {
    if (!clientSideInputCheck(query)) {
      setStreamError('Input failed client-side security checks (SQL injection pattern detected).');
      return;
    }

    setSendingQuery(true);
    setStreamError('');

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...authHeaders(),
    };
    const body = JSON.stringify({
      query,
      session_id: sessionId,
      ...(parentMsgId ? { parent_msg_id: parentMsgId } : {}),
    });

    const abortController = new AbortController();
    abortRef.current = abortController;

    let assistantId = '';
    let userId = '';
    let currentCitations: Citation[] = [];

    try {
      await fetchEventSource(`${API_BASE}/api/query/stream`, {
        method: 'POST',
        headers,
        body,
        signal: abortController.signal,
        async onopen(response) {
          if (response.ok) return;
          let errMsg = `Server returned status ${response.status}`;
          try {
            const errData = await response.json();
            errMsg = errData.detail || errMsg;
          } catch {}
          throw new Error(errMsg);
        },
        onmessage(ev) {
          try {
            const data = JSON.parse(ev.data);
            switch (data.type) {
              case 'text_chunk':
                if (!assistantId) {
                  assistantId = 'pending-' + Date.now();
                  userId = 'pending-user-' + Date.now();
                  onUpdate({
                    type: 'pending',
                    userMsg: {
                      message_id: userId,
                      session_id: sessionId,
                      parent_message_id: parentMsgId,
                      role: 'user',
                      content: query,
                      created_at: new Date().toISOString(),
                    },
                    assistantMsg: {
                      message_id: assistantId,
                      session_id: sessionId,
                      parent_message_id: userId,
                      role: 'assistant',
                      content: '',
                      created_at: new Date().toISOString(),
                    },
                  });
                }
                onUpdate({ type: 'chunk', text: data.content });
                break;
              case 'citation':
                currentCitations.push(data);
                onUpdate({ type: 'citation', data });
                break;
              case 'session':
                if (data.user_message_id && data.message_id) {
                  userId = data.user_message_id;
                  assistantId = data.message_id;
                  onUpdate({ type: 'resolved', userId, assistantId });
                }
                break;
              case 'done':
                onUpdate({ type: 'done', citations: currentCitations });
                setSendingQuery(false);
                abortController.abort();
                break;
              case 'error':
                onUpdate({ type: 'error', detail: data.detail });
                setSendingQuery(false);
                break;
            }
          } catch (err) {
            console.error('Error parsing SSE event:', err);
          }
        },
        onerror(err) {
          if (err.message && /^Server returned status 4/.test(err.message)) {
            onUpdate({ type: 'error', detail: err.message });
            setSendingQuery(false);
            abortController.abort();
            return;
          }
          onUpdate({ type: 'error', detail: err.message || 'Stream connection error' });
          setSendingQuery(false);
          abortController.abort();
          throw err;
        },
      });
    } catch (err: any) {
      onUpdate({ type: 'error', detail: err.message || 'Network error sending query' });
      setSendingQuery(false);
    }
  }, []);

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    setSendingQuery(false);
  }, []);

  return { sendQuery, cancelStream, sendingQuery, streamError, setStreamError };
}
