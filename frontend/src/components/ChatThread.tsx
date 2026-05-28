import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import {
  ThreadPrimitive,
  MessagePrimitive,
  ComposerPrimitive,
  AssistantRuntimeProvider,
  useLocalRuntime,
} from '@assistant-ui/react';
import type { MessageState } from '@assistant-ui/core';
import type { SSEAdapterConfig } from '../lib/sseAdapter';
import { createSSEAdapter } from '../lib/sseAdapter';

interface ChatThreadProps {
  adapterConfig: SSEAdapterConfig;
}

export function ChatThread({ adapterConfig }: ChatThreadProps) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const adapter = createSSEAdapter(adapterConfig);
  const runtime = useLocalRuntime(adapter);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="widget-thread" style={{ display: 'contents' }}>
        <ThreadPrimitive.Viewport className="widget-viewport">
          <ThreadPrimitive.Empty>
            <div className="widget-empty">
              <p className="widget-empty-title">How can we help?</p>
              <p className="widget-empty-subtitle">Ask us anything about AI engineering.</p>
            </div>
          </ThreadPrimitive.Empty>
          <ThreadPrimitive.Messages>
            {({ message }: { message: MessageState }) => <Message message={message} />}
          </ThreadPrimitive.Messages>
        </ThreadPrimitive.Viewport>
        <Composer />
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}

function Message({ message }: { message: MessageState }) {
  const isUser = message.role === 'user';
  const isStreaming =
    !isUser &&
    'status' in message &&
    message.status?.type === 'running';

  const text = message.content
    .filter(p => p.type === 'text')
    .map(p => (p as { type: 'text'; text: string }).text)
    .join('');

  return (
    <MessagePrimitive.Root
      className={`widget-message widget-message--${isUser ? 'user' : 'assistant'}`}
    >
      <div
        className={`widget-message-bubble${isStreaming ? ' is-streaming' : ''}`}
      >
        {text}
      </div>
    </MessagePrimitive.Root>
  );
}

function Composer() {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [value]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const form = e.currentTarget.closest('form');
      form?.requestSubmit();
    }
  }

  return (
    <ComposerPrimitive.Root className="widget-composer">
      <ComposerPrimitive.Input
        ref={textareaRef}
        className="widget-input"
        placeholder="Type a message…"
        rows={1}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
      />
      <ComposerPrimitive.Send
        className="widget-send-btn"
        aria-label="Send message"
        onClick={() => setValue('')}
      >
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
        </svg>
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  );
}
