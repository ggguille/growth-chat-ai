import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  ChatModelRunResult,
} from '@assistant-ui/react';
import type { TextMessagePart } from '@assistant-ui/core';

type SSEEvent =
  | { type: 'token'; content: string }
  | { type: 'done'; session_id: string; lead_level: string; current_stage: number; stage3_proposal_issued: boolean; handoff_reason: string | null; turn_count: number }
  | { type: 'error'; code: string; message: string };

export interface SSEAdapterConfig {
  apiUrl: string;
  sessionId: string;
  apiKey: string;
  onFallback: () => void;
  streamTimeoutMs: number;
  onDone?: (event: Extract<SSEEvent, { type: 'done' }>) => void;
  onError?: (err: Error | null) => void;
}

export function createSSEAdapter(config: SSEAdapterConfig): ChatModelAdapter {
  let turnCount = 0;

  return {
    async *run(options: ChatModelRunOptions): AsyncGenerator<ChatModelRunResult> {
      const { messages, abortSignal } = options;

      config.onError?.(null);

      const lastMessage = messages[messages.length - 1];
      if (!lastMessage || lastMessage.role !== 'user') return;

      const text = lastMessage.content
        .filter((p: unknown): p is TextMessagePart => (p as TextMessagePart).type === 'text')
        .map((p: TextMessagePart) => p.text)
        .join('');

      if (!text.trim()) return;

      const isFirstRequest = turnCount === 0;
      let receivedFirstToken = false;
      let timeoutId: ReturnType<typeof setTimeout> | null = null;

      if (isFirstRequest) {
        timeoutId = setTimeout(() => {
          if (!receivedFirstToken) {
            config.onFallback();
          }
        }, config.streamTimeoutMs);
      }

      let response: Response;
      try {
        response = await fetch(config.apiUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
            'ZGC-Session-ID': config.sessionId,
            'ZGC-API-KEY': config.apiKey,
          },
          body: JSON.stringify({ message: text }),
          signal: abortSignal,
        });
      } catch (err) {
        if (timeoutId) clearTimeout(timeoutId);
        if (isFirstRequest) config.onFallback();
        throw err;
      }

      if (timeoutId) clearTimeout(timeoutId);

      if (response.status === 401 || response.status >= 500) {
        if (isFirstRequest) config.onFallback();
        throw new Error(`HTTP ${response.status}`);
      }

      if (response.status === 429) {
        let errorMessage = 'Too many messages. Please wait before sending another.';
        try {
          const errBody = await response.json() as { error?: { message?: string } };
          if (errBody.error?.message) errorMessage = errBody.error.message;
        } catch {
          // non-JSON body — use default message
        }
        const err = new Error(errorMessage);
        config.onError?.(err);
        throw err;
      }

      if (!response.body) {
        if (isFirstRequest) config.onFallback();
        throw new Error('Empty response body');
      }

      turnCount++;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulatedText = '';
      let isStreaming = true;

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop() ?? '';

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data: ')) continue;

            let event: SSEEvent;
            try {
              event = JSON.parse(line.slice(6)) as SSEEvent;
            } catch {
              continue;
            }

            if (event.type === 'token') {
              if (!receivedFirstToken) receivedFirstToken = true;
              accumulatedText += event.content;
              yield { content: [{ type: 'text', text: accumulatedText }] };
            } else if (event.type === 'done') {
              isStreaming = false;
              config.onDone?.(event);
            } else if (event.type === 'error') {
              throw new Error(event.message);
            }
          }
        }
      } finally {
        isStreaming;
        reader.releaseLock();
      }
    },
  };
}
