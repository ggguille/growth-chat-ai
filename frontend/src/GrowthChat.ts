import { createRoot, Root } from 'react-dom/client';
import { createElement } from 'react';
import { ChatWidget } from './components/ChatWidget';

export class GrowthChat extends HTMLElement {
  static observedAttributes = ['api-url'];

  private root: Root | null = null;
  private mountPoint: HTMLDivElement | null = null;

  connectedCallback(): void {
    const shadow = this.attachShadow({ mode: 'open' });
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
      })
    );
  }
}
