interface FallbackViewProps {
  fallbackUrl: string;
}

export function FallbackView({ fallbackUrl }: FallbackViewProps) {
  return (
    <div className="widget-fallback" role="status">
      <div className="widget-fallback-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
        </svg>
      </div>
      <p className="widget-fallback-text">
        Our chat assistant isn't available right now. You can still reach us using our contact
        form.
      </p>
      {fallbackUrl && (
        <a
          className="widget-fallback-link"
          href={fallbackUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Contact us
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z" />
          </svg>
        </a>
      )}
    </div>
  );
}
