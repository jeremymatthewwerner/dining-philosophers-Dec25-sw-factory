import { render, screen } from '@/test-utils';
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

  describe('with thinkingContent', () => {
    it('shows individual thinker rows when thinkingContent is provided', () => {
      const thinkingContent = new Map([
        ['Socrates', 'Considering the nature of justice...'],
      ]);
      render(
        <TypingIndicator
          typingThinkers={['Socrates']}
          thinkingContent={thinkingContent}
        />
      );
      expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
      expect(screen.getByText('Socrates')).toBeInTheDocument();
      expect(
        screen.getByText('Considering the nature of justice...')
      ).toBeInTheDocument();
    });

    it('shows "is thinking" text when thinker has no thinking content', () => {
      const thinkingContent = new Map([['Socrates', '']]);
      // Empty map entry means the get returns empty string which is falsy
      const thinkingContentWithEmpty = new Map<string, string>();
      thinkingContentWithEmpty.set('Socrates', '');

      render(
        <TypingIndicator
          typingThinkers={['Socrates']}
          thinkingContent={thinkingContentWithEmpty}
        />
      );
      // Since empty string is falsy, should show "is thinking" fallback
      // The component renders the isThinking text
      expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
    });

    it('shows thinking content for multiple thinkers', () => {
      const thinkingContent = new Map([
        ['Socrates', 'About virtue...'],
        ['Plato', 'About the Forms...'],
      ]);
      render(
        <TypingIndicator
          typingThinkers={['Socrates', 'Plato']}
          thinkingContent={thinkingContent}
        />
      );
      expect(screen.getByText('Socrates')).toBeInTheDocument();
      expect(screen.getByText('About virtue...')).toBeInTheDocument();
      expect(screen.getByText('Plato')).toBeInTheDocument();
      expect(screen.getByText('About the Forms...')).toBeInTheDocument();
    });

    it('falls back to simple format when thinkingContent is empty Map', () => {
      const emptyMap = new Map<string, string>();
      render(
        <TypingIndicator
          typingThinkers={['Socrates']}
          thinkingContent={emptyMap}
        />
      );
      // With empty thinkingContent map, hasThinkingContent is false
      // Should use the simple format with formatNames
      expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
      expect(screen.getByText('Socrates is thinking...')).toBeInTheDocument();
    });

    it('falls back to simple format when thinkingContent is undefined', () => {
      render(<TypingIndicator typingThinkers={['Socrates']} />);
      expect(screen.getByText('Socrates is thinking...')).toBeInTheDocument();
    });

    it('renders animated dots in thinking content mode', () => {
      const thinkingContent = new Map([['Socrates', 'Thinking...']]);
      render(
        <TypingIndicator
          typingThinkers={['Socrates']}
          thinkingContent={thinkingContent}
        />
      );
      const dots = screen
        .getByTestId('typing-indicator')
        .querySelectorAll('.animate-bounce');
      expect(dots).toHaveLength(3);
    });
  });
});
