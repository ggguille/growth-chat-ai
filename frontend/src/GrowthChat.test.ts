import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest';

// Mock CSS inline import
vi.mock('./styles/widget.css?inline', () => ({ default: '' }));

// Mock import.meta.env
vi.stubEnv('VITE_API_URL', 'http://localhost:8000/chat');
vi.stubEnv('VITE_FALLBACK_URL', 'http://localhost:5173/contact');
vi.stubEnv('VITE_API_KEY', 'dev-key');

// Mock ChatWidget render to avoid full React tree
vi.mock('./components/ChatWidget', () => ({
  ChatWidget: vi.fn(() => null),
}));

const UUID_V4_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('GrowthChat web component', () => {
  beforeAll(async () => {
    const { GrowthChat } = await import('./GrowthChat');
    if (!customElements.get('growth-chat')) {
      customElements.define('growth-chat', GrowthChat);
    }
  });

  afterEach(() => {
    sessionStorage.clear();
    document.body.innerHTML = '';
  });

  it('registers as growth-chat custom element', () => {
    expect(customElements.get('growth-chat')).toBeDefined();
  });

  it('generates a valid UUID v4 session ID on connect', async () => {
    const el = document.createElement('growth-chat') as HTMLElement;
    document.body.appendChild(el);
    await customElements.whenDefined('growth-chat');
    const sessionId = sessionStorage.getItem('zgc-session-id');
    expect(sessionId).toMatch(UUID_V4_RE);
  });

  it('reuses the same session ID across re-renders', async () => {
    const el = document.createElement('growth-chat') as HTMLElement;
    document.body.appendChild(el);
    const id1 = sessionStorage.getItem('zgc-session-id');
    document.body.removeChild(el);
    const el2 = document.createElement('growth-chat') as HTMLElement;
    document.body.appendChild(el2);
    const id2 = sessionStorage.getItem('zgc-session-id');
    expect(id1).toBe(id2);
  });

  it('observes fallback-url attribute', () => {
    expect((customElements.get('growth-chat') as typeof HTMLElement & { observedAttributes?: string[] })?.observedAttributes).toContain('fallback-url');
  });

  it('observes api-key attribute', () => {
    expect((customElements.get('growth-chat') as typeof HTMLElement & { observedAttributes?: string[] })?.observedAttributes).toContain('api-key');
  });

  it('observes api-url attribute', () => {
    expect((customElements.get('growth-chat') as typeof HTMLElement & { observedAttributes?: string[] })?.observedAttributes).toContain('api-url');
  });
});
