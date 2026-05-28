import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GDPRNotice } from '../GDPRNotice';

describe('GDPRNotice', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('renders the provided GDPR text', () => {
    render(
      <GDPRNotice
        text="We process your data in accordance with GDPR."
        hostElement={null}
        onAccept={vi.fn()}
      />
    );
    expect(screen.getByText('We process your data in accordance with GDPR.')).toBeInTheDocument();
  });

  it('renders a default text when none is provided', () => {
    render(<GDPRNotice text="" hostElement={null} onAccept={vi.fn()} />);
    expect(screen.getByText(/powered by AI/i)).toBeInTheDocument();
  });

  it('renders the accept button', () => {
    render(<GDPRNotice text="notice" hostElement={null} onAccept={vi.fn()} />);
    expect(screen.getByRole('button', { name: /got it/i })).toBeInTheDocument();
  });

  it('calls onAccept when the button is clicked', async () => {
    const onAccept = vi.fn();
    render(<GDPRNotice text="notice" hostElement={null} onAccept={onAccept} />);
    await userEvent.click(screen.getByRole('button', { name: /got it/i }));
    expect(onAccept).toHaveBeenCalledOnce();
  });

  it('persists acceptance to sessionStorage', async () => {
    render(<GDPRNotice text="notice" hostElement={null} onAccept={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /got it/i }));
    expect(sessionStorage.getItem('zgc-gdpr-accepted')).toBe('1');
  });

  it('dispatches zgc:gdpr_acknowledged on the host element when accepted', async () => {
    const host = document.createElement('div');
    const listener = vi.fn();
    host.addEventListener('zgc:gdpr_acknowledged', listener);

    render(<GDPRNotice text="notice" hostElement={host} onAccept={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /got it/i }));

    expect(listener).toHaveBeenCalledOnce();
  });
});
