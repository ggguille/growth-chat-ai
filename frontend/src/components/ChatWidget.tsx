interface ChatWidgetProps {
  apiUrl: string;
}

export function ChatWidget({ apiUrl }: ChatWidgetProps) {
  return (
    <div style={{ fontFamily: 'sans-serif', padding: '1rem', border: '1px solid #ccc' }}>
      <p>Growth Chat</p>
      <p style={{ fontSize: '0.75rem', color: '#666' }}>{apiUrl || '(no api-url set)'}</p>
    </div>
  );
}
