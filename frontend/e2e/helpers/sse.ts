export interface SseEvent {
  type: 'token' | 'done' | 'error';
  [key: string]: unknown;
}

/**
 * Parses a complete SSE response body string and returns all events found.
 * Each event is expected on a `data: <json>` line separated by double newlines.
 */
export async function collectSseEvents(responseBody: string): Promise<SseEvent[]> {
  const events: SseEvent[] = [];
  for (const line of responseBody.split('\n')) {
    if (line.startsWith('data: ')) {
      try {
        events.push(JSON.parse(line.slice(6)) as SseEvent);
      } catch {
        // ignore malformed lines
      }
    }
  }
  return events;
}
