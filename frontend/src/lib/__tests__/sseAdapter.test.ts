import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createSSEAdapter } from '../sseAdapter';
import type { SSEAdapterConfig } from '../sseAdapter';
import type { ChatModelRunOptions, ChatModelRunResult } from '@assistant-ui/react';

function runGen(adapter: ReturnType<typeof createSSEAdapter>, options: ChatModelRunOptions): AsyncGenerator<ChatModelRunResult> {
  return adapter.run(options) as AsyncGenerator<ChatModelRunResult>;
}

function makeOptions(userText: string): ChatModelRunOptions {
  return {
    messages: [
      {
        id: 'msg-1',
        role: 'user',
        content: [{ type: 'text', text: userText }],
      } as never,
    ],
    abortSignal: new AbortController().signal,
    runConfig: {},
    context: { tools: [], system: undefined, modelConfig: {} },
    unstable_getMessage: () => { throw new Error('not used'); },
  } as unknown as ChatModelRunOptions;
}

function makeSseStream(events: object[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const chunks = events.map(e => encoder.encode(`data: ${JSON.stringify(e)}\n\n`));
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  });
}

function makeConfig(overrides: Partial<SSEAdapterConfig> = {}): SSEAdapterConfig {
  return {
    apiUrl: 'https://api.test/chat',
    sessionId: '00000000-0000-4000-8000-000000000001',
    apiKey: 'test-key',
    onFallback: vi.fn(),
    streamTimeoutMs: 5000,
    ...overrides,
  };
}

describe('sseAdapter', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('sends correct headers on every request', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        makeSseStream([
          { type: 'token', content: 'hi' },
          { type: 'done', session_id: 'x', lead_level: 'cold', current_stage: 1, stage3_proposal_issued: false, handoff_reason: null, turn_count: 1 },
        ]),
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
      )
    );

    const adapter = createSSEAdapter(makeConfig());
    for await (const _ of runGen(adapter, makeOptions('hello'))) { /* drain */ }

    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.test/chat');
    const headers = init.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['Accept']).toBe('text/event-stream');
    expect(headers['ZGC-Session-ID']).toBe('00000000-0000-4000-8000-000000000001');
    expect(headers['ZGC-API-KEY']).toBe('test-key');
  });

  it('yields accumulated text from token events', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        makeSseStream([
          { type: 'token', content: 'Hello' },
          { type: 'token', content: ' world' },
          { type: 'done', session_id: 'x', lead_level: 'cold', current_stage: 1, stage3_proposal_issued: false, handoff_reason: null, turn_count: 1 },
        ]),
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
      )
    );

    const adapter = createSSEAdapter(makeConfig());
    const updates: string[] = [];
    for await (const update of runGen(adapter, makeOptions('hi'))) {
      const textPart = update.content?.find((p: { type: string }) => p.type === 'text');
      if (textPart && 'text' in textPart) updates.push((textPart as { text: string }).text);
    }

    expect(updates).toEqual(['Hello', 'Hello world']);
  });

  it('calls onDone with the done event payload', async () => {
    const onDone = vi.fn();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        makeSseStream([
          { type: 'token', content: 'ok' },
          { type: 'done', session_id: 'sess-1', lead_level: 'warm', current_stage: 2, stage3_proposal_issued: false, handoff_reason: null, turn_count: 3 },
        ]),
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
      )
    );

    const adapter = createSSEAdapter(makeConfig({ onDone }));
    for await (const _ of runGen(adapter, makeOptions('x'))) { /* drain */ }

    expect(onDone).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'done', lead_level: 'warm', current_stage: 2 })
    );
  });

  it('throws on SSE error event', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        makeSseStream([
          { type: 'error', code: 'ORCHESTRATOR_ERROR', message: 'Something went wrong' },
        ]),
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
      )
    );

    const adapter = createSSEAdapter(makeConfig());
    await expect(async () => {
      for await (const _ of runGen(adapter, makeOptions('x'))) { /* drain */ }
    }).rejects.toThrow('Something went wrong');
  });

  describe('first request — fallback activation', () => {
    it('calls onFallback on network error (first request)', async () => {
      const config = makeConfig();
      vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

      const adapter = createSSEAdapter(config);
      await expect(async () => {
        for await (const _ of runGen(adapter, makeOptions('x'))) { /* drain */ }
      }).rejects.toThrow();
      expect(config.onFallback).toHaveBeenCalledOnce();
    });

    it('calls onFallback on HTTP 503 (first request)', async () => {
      const config = makeConfig();
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ error: { code: 'SERVICE_UNAVAILABLE' } }), { status: 503 })
      );

      const adapter = createSSEAdapter(config);
      await expect(async () => {
        for await (const _ of runGen(adapter, makeOptions('x'))) { /* drain */ }
      }).rejects.toThrow('HTTP 503');
      expect(config.onFallback).toHaveBeenCalledOnce();
    });

    it('calls onFallback on HTTP 401 (first request)', async () => {
      const config = makeConfig();
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ error: { code: 'INVALID_API_KEY' } }), { status: 401 })
      );

      const adapter = createSSEAdapter(config);
      await expect(async () => {
        for await (const _ of runGen(adapter, makeOptions('x'))) { /* drain */ }
      }).rejects.toThrow('HTTP 401');
      expect(config.onFallback).toHaveBeenCalledOnce();
    });
  });

  describe('subsequent requests — no fallback', () => {
    it('does NOT call onFallback on HTTP 503 after first turn succeeds', async () => {
      const config = makeConfig();
      const fetchSpy = vi.spyOn(globalThis, 'fetch');

      // First request succeeds
      fetchSpy.mockResolvedValueOnce(
        new Response(
          makeSseStream([
            { type: 'token', content: 'ok' },
            { type: 'done', session_id: 'x', lead_level: 'cold', current_stage: 1, stage3_proposal_issued: false, handoff_reason: null, turn_count: 1 },
          ]),
          { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
        )
      );
      // Second request fails with 503
      fetchSpy.mockResolvedValueOnce(
        new Response('', { status: 503 })
      );

      const adapter = createSSEAdapter(config);

      // First turn
      for await (const _ of runGen(adapter, makeOptions('turn 1'))) { /* drain */ }

      // Second turn — should throw but NOT call onFallback
      await expect(async () => {
        for await (const _ of runGen(adapter, makeOptions('turn 2'))) { /* drain */ }
      }).rejects.toThrow('HTTP 503');

      expect(config.onFallback).not.toHaveBeenCalled();
    });
  });

  it('calls onFallback on stream timeout (first request, no tokens)', async () => {
    vi.useFakeTimers();
    const config = makeConfig({ streamTimeoutMs: 100 });

    // Request that never resolves
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => { /* never resolves */ })
    );

    const adapter = createSSEAdapter(config);
    const runPromise = (async () => {
      for await (const _ of runGen(adapter, makeOptions('x'))) { /* drain */ }
    })();

    await vi.advanceTimersByTimeAsync(150);

    expect(config.onFallback).toHaveBeenCalledOnce();

    // Clean up
    runPromise.catch(() => {});
    vi.useRealTimers();
  });
});
