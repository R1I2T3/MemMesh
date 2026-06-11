import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { UserIcon, BotIcon, GitBranchIcon, ThumbsUpIcon, ThumbsDownIcon } from 'lucide-react';
import { CitationButton } from './CitationButton';
import type { Message, Citation } from '@/types/api';

interface ChatMessageProps {
  message: Message;
  onBranch: (msgId: string) => void;
  onFeedback?: (msgId: string, rating: number) => void;
  onCitationClick?: (citation: Citation) => void;
  ratings?: Record<string, number>;
  children?: React.ReactNode;
}

function renderMessageContent(
  msg: Message,
  onCitationClick?: (citation: Citation) => void,
) {
  const hasCitations = msg.role === 'assistant' && msg.citations && msg.citations.length > 0;

  const processed = hasCitations
    ? msg.content.replace(
        /\[(?:Web\s+)?(\d+)\]/g,
        (match, num) => `<span data-idx="${parseInt(num) - 1}">${match}</span>`,
      )
    : msg.content;

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none break-words leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          span: ({ children, ...props }) => {
            const dataIdx = (props as any)['data-idx'];
            if (dataIdx !== undefined) {
              const idx = parseInt(dataIdx, 10);
              const citation = msg.citations?.[idx];
              if (citation && onCitationClick) {
                return (
                  <CitationButton
                    onClick={() => onCitationClick(citation)}
                    title={`View source: ${citation.source || citation.url || 'Document'}`}
                  >
                    {children}
                  </CitationButton>
                );
              }
              return <span className="font-mono text-xs">{children}</span>;
            }
            return <span>{children}</span>;
          },
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
}

export function ChatMessage({ message, onBranch, onFeedback, onCitationClick, ratings, children }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className="flex flex-col gap-1.5 group">
      <div className={`flex gap-3 max-w-[85%] ${isUser ? 'self-end flex-row-reverse' : 'self-start'}`}>
        <div
          className={`size-8 rounded-xl flex items-center justify-center flex-shrink-0 ring-1 ${
            isUser
              ? 'bg-gradient-to-br from-indigo-500 to-indigo-600 text-white ring-indigo-500/20 shadow-sm'
              : 'bg-muted ring-border/50'
          }`}
        >
          {isUser ? <UserIcon className="size-[15px]" /> : <BotIcon className="size-[15px] text-foreground/70" />}
        </div>

        <div className="flex flex-col gap-1 min-w-0">
          <div
            className={`px-4 py-3 rounded-2xl relative border text-sm leading-relaxed transition-all duration-200 ${
              isUser
                ? 'bg-gradient-to-br from-indigo-500 to-indigo-600 border-indigo-400/30 text-white rounded-tr-none shadow-sm shadow-indigo-500/10'
                : 'bg-card border-border/60 text-foreground rounded-tl-none shadow-sm'
            }`}
          >
            {renderMessageContent(message, onCitationClick)}

            {!isUser && onFeedback && (
              <div className="flex items-center gap-1.5 mt-3 pt-2 border-t border-border/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                <button
                  type="button"
                  onClick={() => onFeedback(message.message_id, 1)}
                  className={`p-1 rounded-md hover:bg-muted transition-colors flex items-center justify-center ${
                    ratings?.[message.message_id] === 1
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-muted-foreground/50 hover:text-muted-foreground'
                  }`}
                  title="Thumbs Up"
                >
                  <ThumbsUpIcon className="size-[14px]" />
                </button>
                <button
                  type="button"
                  onClick={() => onFeedback(message.message_id, -1)}
                  className={`p-1 rounded-md hover:bg-muted transition-colors flex items-center justify-center ${
                    ratings?.[message.message_id] === -1
                      ? 'text-red-500 dark:text-red-400'
                      : 'text-muted-foreground/50 hover:text-muted-foreground'
                  }`}
                  title="Thumbs Down"
                >
                  <ThumbsDownIcon className="size-[14px]" />
                </button>
              </div>
            )}
          </div>

          <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} px-1`}>
            <button
              type="button"
              onClick={() => onBranch(message.message_id)}
              className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/40 hover:text-primary transition-colors opacity-0 group-hover:opacity-100"
            >
              <GitBranchIcon className="size-3" />
              <span>Branch</span>
            </button>
          </div>
        </div>
      </div>

      {children}
    </div>
  );
}
