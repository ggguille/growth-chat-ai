import { useState, useEffect } from 'react';
import { GDPRNotice, isGdprAccepted } from './GDPRNotice';
import { FallbackView } from './FallbackView';
import { ChatThread } from './ChatThread';
import type { SSEAdapterConfig } from '../lib/sseAdapter';

export interface ChatWidgetProps {
  apiUrl: string;
  fallbackUrl: string;
  apiKey: string;
  sessionId: string;
  gdprNoticeText?: string;
  streamTimeoutMs?: number;
  proactiveDelayMs?: number;
  hostElement?: HTMLElement | null;
}

export function ChatWidget({
  apiUrl,
  fallbackUrl,
  apiKey,
  sessionId,
  gdprNoticeText = '',
  streamTimeoutMs = 10_000,
  proactiveDelayMs = 45_000,
  hostElement = null,
}: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [gdprAccepted, setGdprAccepted] = useState(isGdprAccepted);
  const [fallbackActive, setFallbackActive] = useState(false);
  const [showProactivePrompt, setShowProactivePrompt] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setShowProactivePrompt(false);
      return;
    }
    const timer = setTimeout(() => setShowProactivePrompt(true), proactiveDelayMs);
    return () => clearTimeout(timer);
  }, [isOpen, proactiveDelayMs]);

  const adapterConfig: SSEAdapterConfig = {
    apiUrl,
    apiKey,
    sessionId,
    streamTimeoutMs,
    onFallback: () => setFallbackActive(true),
    onDone: event => {
      hostElement?.dispatchEvent(
        new CustomEvent('zgc:qualification_state_changed', {
          bubbles: true,
          composed: true,
          detail: { leadLevel: event.lead_level, currentStage: event.current_stage },
        })
      );
      if (event.stage3_proposal_issued) {
        hostElement?.dispatchEvent(
          new CustomEvent('zgc:escalation_triggered', {
            bubbles: true,
            composed: true,
            detail: { handoffReason: event.handoff_reason },
          })
        );
      }
    },
  };

  function renderPanel() {
    if (fallbackActive) return <FallbackView fallbackUrl={fallbackUrl} />;
    if (!gdprAccepted)
      return (
        <GDPRNotice
          text={gdprNoticeText}
          hostElement={hostElement}
          onAccept={() => setGdprAccepted(true)}
        />
      );
    return <ChatThread adapterConfig={adapterConfig} />;
  }

  return (
    <>
      {isOpen && (
        <div className="widget-panel" role="dialog" aria-label="Chat">
          <div className="widget-header">
            <div>
              <div className="widget-header-title">Chat with us</div>
              <div className="widget-header-subtitle">We typically reply in minutes</div>
            </div>
            <button
              className="widget-close-btn"
              onClick={() => setIsOpen(false)}
              aria-label="Close chat"
              type="button"
            >
              <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
              </svg>
            </button>
          </div>
          {renderPanel()}
        </div>
      )}

      {showProactivePrompt && !isOpen && (
        <div className="widget-proactive" data-testid="proactive-prompt">
          <p className="widget-proactive-text">Have questions about AI engineering?</p>
          <button
            type="button"
            className="widget-proactive-cta"
            onClick={() => {
              setIsOpen(true);
              setShowProactivePrompt(false);
            }}
          >
            Let's chat
          </button>
        </div>
      )}

      <button
        data-testid="launcher-button"
        className="widget-launcher"
        onClick={() => setIsOpen(o => !o)}
        aria-label={isOpen ? 'Toggle chat' : 'Open chat'}
        aria-expanded={isOpen}
        type="button"
      >
        {isOpen ? (
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
          </svg>
        )}
      </button>
    </>
  );
}
