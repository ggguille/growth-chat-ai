import { createRoot, type Root } from 'react-dom/client';
import { createElement } from 'react';
import { ChatWidget } from './components/ChatWidget';
import widgetStyles from './styles/widget.css?inline';

const SESSION_ID_KEY = 'zgc-session-id';

function getOrCreateSessionId(): string {
  try {
    const existing = sessionStorage.getItem(SESSION_ID_KEY);
    if (existing) return existing;
    const id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_ID_KEY, id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

export class GrowthChat extends HTMLElement {
  static observedAttributes = ['api-url', 'fallback-url', 'api-key', 'proactive-delay-ms'];

  private root: Root | null = null;
  private mountPoint: HTMLDivElement | null = null;
  private sessionId: string = '';

  connectedCallback(): void {
    this.sessionId = getOrCreateSessionId();

    const shadow = this.attachShadow({ mode: 'open' });

    const styleEl = document.createElement('style');
    styleEl.textContent = widgetStyles;
    shadow.appendChild(styleEl);

    this.mountPoint = document.createElement('div');
    shadow.appendChild(this.mountPoint);

    this.root = createRoot(this.mountPoint);
    this.render();
  }

  disconnectedCallback(): void {
    this.root?.unmount();
    this.root = null;
    this.mountPoint = null;
  }

  attributeChangedCallback(): void {
    this.render();
  }

  private render(): void {
    if (!this.root) return;
    this.root.render(
      createElement(ChatWidget, {
        apiUrl: this.getAttribute('api-url') ?? import.meta.env.VITE_API_URL ?? '',
        fallbackUrl: this.getAttribute('fallback-url') ?? import.meta.env.VITE_FALLBACK_URL ?? '',
        apiKey: this.getAttribute('api-key') ?? import.meta.env.VITE_API_KEY ?? '',
        sessionId: this.sessionId,
        gdprNoticeText: import.meta.env.VITE_GDPR_NOTICE_TEXT ?? '',
        streamTimeoutMs: Number(import.meta.env.VITE_STREAM_TIMEOUT_MS) || 10_000,
        proactiveDelayMs: Number(this.getAttribute('proactive-delay-ms')) || 45_000,
        hostElement: this,
      })
    );
  }
}
