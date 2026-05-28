import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FallbackView } from '../FallbackView';

describe('FallbackView', () => {
  it('renders the fallback message', () => {
    render(<FallbackView fallbackUrl="https://example.com/contact" />);
    expect(screen.getByText(/isn't available right now/i)).toBeInTheDocument();
  });

  it('renders a link with the provided fallback URL', () => {
    render(<FallbackView fallbackUrl="https://example.com/contact" />);
    const link = screen.getByRole('link', { name: /contact us/i });
    expect(link).toHaveAttribute('href', 'https://example.com/contact');
  });

  it('opens the link in a new tab', () => {
    render(<FallbackView fallbackUrl="https://example.com/contact" />);
    const link = screen.getByRole('link', { name: /contact us/i });
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('does not render the link when fallbackUrl is empty', () => {
    render(<FallbackView fallbackUrl="" />);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
