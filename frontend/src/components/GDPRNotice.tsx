const GDPR_SESSION_KEY = 'zgc-gdpr-accepted';

interface GDPRNoticeProps {
  text: string;
  hostElement: HTMLElement | null;
  onAccept: () => void;
}

export function GDPRNotice({ text, hostElement, onAccept }: GDPRNoticeProps) {
  function handleAccept() {
    try {
      sessionStorage.setItem(GDPR_SESSION_KEY, '1');
    } catch {
      // sessionStorage may be unavailable in some contexts
    }
    hostElement?.dispatchEvent(
      new CustomEvent('zgc:gdpr_acknowledged', { bubbles: true, composed: true })
    );
    onAccept();
  }

  return (
    <div className="widget-gdpr" role="dialog" aria-label="Data notice">
      <div className="widget-gdpr-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-1 6h2v2h-2V7zm0 4h2v6h-2v-6z" />
        </svg>
      </div>
      <p className="widget-gdpr-text">
        {text ||
          'This chat is powered by AI. Messages you send may be processed to help us respond to your enquiry. By continuing you agree to this.'}
      </p>
      <button className="widget-gdpr-accept" data-testid="gdpr-accept" onClick={handleAccept} type="button">
        Got it — let's chat
      </button>
    </div>
  );
}

export function isGdprAccepted(): boolean {
  try {
    return sessionStorage.getItem(GDPR_SESSION_KEY) === '1';
  } catch {
    return false;
  }
}
