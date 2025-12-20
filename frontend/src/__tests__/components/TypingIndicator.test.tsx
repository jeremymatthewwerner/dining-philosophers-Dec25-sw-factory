import { render, screen } from '@testing-library/react';
import { TypingIndicator } from '@/components/TypingIndicator';

describe('TypingIndicator', () => {
  it('renders nothing when no thinkers are typing', () => {
    const { container } = render(<TypingIndicator typingThinkers={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders single thinker typing', () => {
    render(<TypingIndicator typingThinkers={['Socrates']} />);
    expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
    expect(screen.getByText('Socrates is thinking...')).toBeInTheDocument();
  });

  it('renders two thinkers typing', () => {
    render(<TypingIndicator typingThinkers={['Socrates', 'Plato']} />);
    expect(
      screen.getByText('Socrates and Plato are thinking...')
    ).toBeInTheDocument();
  });

  it('renders three or more thinkers typing', () => {
    render(
      <TypingIndicator typingThinkers={['Socrates', 'Plato', 'Aristotle']} />
    );
    expect(
      screen.getByText('Socrates, Plato, and Aristotle are thinking...')
    ).toBeInTheDocument();
  });

  it('renders animated dots', () => {
    render(<TypingIndicator typingThinkers={['Socrates']} />);
    const dots = screen
      .getByTestId('typing-indicator')
      .querySelectorAll('.animate-bounce');
    expect(dots).toHaveLength(3);
  });
});
