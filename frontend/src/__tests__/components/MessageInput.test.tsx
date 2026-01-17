import { fireEvent, render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import { MessageInput } from '@/components/MessageInput';
import type { ConversationThinker } from '@/types';

// Mock userEvent setup
const user = userEvent.setup();

const mockThinkers: ConversationThinker[] = [
  {
    id: '1',
    name: 'Socrates',
    bio: 'Greek philosopher',
    positions: 'Knowledge is virtue',
    style: 'Questioning',
    color: '#3B82F6',
    image_url: null,
  },
  {
    id: '2',
    name: 'Plato',
    bio: 'Greek philosopher',
    positions: 'Theory of Forms',
    style: 'Dialogic',
    color: '#10B981',
    image_url: null,
  },
  {
    id: '3',
    name: 'Friedrich Nietzsche',
    bio: 'German philosopher',
    positions: 'Will to power',
    style: 'Aphoristic',
    color: '#EF4444',
    image_url: null,
  },
];

describe('MessageInput', () => {
  it('renders input and send button', () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    expect(screen.getByTestId('message-input')).toBeInTheDocument();
    expect(screen.getByTestId('message-textarea')).toBeInTheDocument();
    expect(screen.getByTestId('send-button')).toBeInTheDocument();
  });

  it('calls onSend when form is submitted', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello, world!');
    await user.click(screen.getByTestId('send-button'));

    expect(onSend).toHaveBeenCalledWith('Hello, world!');
  });

  it('clears input after sending', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello!');
    await user.click(screen.getByTestId('send-button'));

    expect(textarea).toHaveValue('');
  });

  it('does not send empty message', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    await user.click(screen.getByTestId('send-button'));

    expect(onSend).not.toHaveBeenCalled();
  });

  it('does not send whitespace-only message', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '   ');
    await user.click(screen.getByTestId('send-button'));

    expect(onSend).not.toHaveBeenCalled();
  });

  it('sends on Enter key (without Shift)', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello!');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    expect(onSend).toHaveBeenCalledWith('Hello!');
  });

  it('does not send on Shift+Enter', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello!');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });

    expect(onSend).not.toHaveBeenCalled();
  });

  it('disables input when disabled prop is true', () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} disabled />);

    expect(screen.getByTestId('message-textarea')).toBeDisabled();
    expect(screen.getByTestId('send-button')).toBeDisabled();
  });

  it('shows custom placeholder', () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} placeholder="Custom placeholder" />);

    expect(
      screen.getByPlaceholderText('Custom placeholder')
    ).toBeInTheDocument();
  });

  it('calls onTypingStart when user starts typing', async () => {
    const onSend = jest.fn();
    const onTypingStart = jest.fn();
    render(<MessageInput onSend={onSend} onTypingStart={onTypingStart} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'H');

    expect(onTypingStart).toHaveBeenCalled();
  });
});

describe('MessageInput - @mention autocomplete', () => {
  it('shows autocomplete dropdown when @ is typed', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');

    expect(screen.getByTestId('mention-autocomplete')).toBeInTheDocument();
  });

  it('does not show autocomplete when no thinkers provided', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');

    expect(
      screen.queryByTestId('mention-autocomplete')
    ).not.toBeInTheDocument();
  });

  it('filters thinkers as user types after @', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@Soc');

    expect(screen.getByTestId('mention-autocomplete')).toBeInTheDocument();
    expect(screen.getByTestId('mention-option-socrates')).toBeInTheDocument();
    expect(
      screen.queryByTestId('mention-option-plato')
    ).not.toBeInTheDocument();
  });

  it('hides autocomplete when no thinkers match query', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@xyz');

    expect(
      screen.queryByTestId('mention-autocomplete')
    ).not.toBeInTheDocument();
  });

  it('inserts thinker name when clicking autocomplete option', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');
    await user.click(screen.getByTestId('mention-option-socrates'));

    expect(textarea).toHaveValue('Socrates');
    expect(
      screen.queryByTestId('mention-autocomplete')
    ).not.toBeInTheDocument();
  });

  it('navigates autocomplete with arrow keys', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');

    // First item should be selected by default
    expect(screen.getByTestId('mention-option-socrates')).toHaveAttribute(
      'aria-selected',
      'true'
    );

    // Navigate down
    fireEvent.keyDown(textarea, { key: 'ArrowDown' });
    await waitFor(() => {
      expect(screen.getByTestId('mention-option-plato')).toHaveAttribute(
        'aria-selected',
        'true'
      );
    });

    // Navigate down again
    fireEvent.keyDown(textarea, { key: 'ArrowDown' });
    await waitFor(() => {
      expect(
        screen.getByTestId('mention-option-friedrich-nietzsche')
      ).toHaveAttribute('aria-selected', 'true');
    });

    // Navigate up
    fireEvent.keyDown(textarea, { key: 'ArrowUp' });
    await waitFor(() => {
      expect(screen.getByTestId('mention-option-plato')).toHaveAttribute(
        'aria-selected',
        'true'
      );
    });
  });

  it('selects thinker with Enter key when autocomplete is active', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');
    fireEvent.keyDown(textarea, { key: 'Enter' });

    expect(textarea).toHaveValue('Socrates');
    expect(onSend).not.toHaveBeenCalled(); // Should not send the message
  });

  it('selects thinker with Tab key when autocomplete is active', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');
    fireEvent.keyDown(textarea, { key: 'Tab' });

    expect(textarea).toHaveValue('Socrates');
  });

  it('closes autocomplete with Escape key', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');
    expect(screen.getByTestId('mention-autocomplete')).toBeInTheDocument();

    fireEvent.keyDown(textarea, { key: 'Escape' });
    expect(
      screen.queryByTestId('mention-autocomplete')
    ).not.toBeInTheDocument();
  });

  it('preserves text before @ when inserting mention', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello @');
    await user.click(screen.getByTestId('mention-option-socrates'));

    expect(textarea).toHaveValue('Hello Socrates');
  });

  it('handles @ at start of message', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');
    await user.click(screen.getByTestId('mention-option-plato'));

    expect(textarea).toHaveValue('Plato');
  });

  it('does not show autocomplete when @ is not at word boundary', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'email@');

    expect(
      screen.queryByTestId('mention-autocomplete')
    ).not.toBeInTheDocument();
  });

  it('shows autocomplete when @ follows newline', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    // Type first line, then newline (Shift+Enter), then @
    await user.type(textarea, 'First line');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    fireEvent.change(textarea, { target: { value: 'First line\n@' } });

    expect(screen.getByTestId('mention-autocomplete')).toBeInTheDocument();
  });

  it('wraps around when navigating past last thinker', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');

    // Navigate to last item
    fireEvent.keyDown(textarea, { key: 'ArrowDown' });
    fireEvent.keyDown(textarea, { key: 'ArrowDown' });
    await waitFor(() => {
      expect(
        screen.getByTestId('mention-option-friedrich-nietzsche')
      ).toHaveAttribute('aria-selected', 'true');
    });

    // Navigate one more - should wrap to first
    fireEvent.keyDown(textarea, { key: 'ArrowDown' });
    await waitFor(() => {
      expect(screen.getByTestId('mention-option-socrates')).toHaveAttribute(
        'aria-selected',
        'true'
      );
    });
  });

  it('wraps around when navigating before first thinker', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');

    // Navigate up from first - should wrap to last
    fireEvent.keyDown(textarea, { key: 'ArrowUp' });
    await waitFor(() => {
      expect(
        screen.getByTestId('mention-option-friedrich-nietzsche')
      ).toHaveAttribute('aria-selected', 'true');
    });
  });

  it('clears autocomplete state when message is sent', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello @');
    await user.click(screen.getByTestId('mention-option-socrates'));

    // Now send the message
    await user.click(screen.getByTestId('send-button'));

    // Type @ again - should show all thinkers (state reset)
    await user.type(textarea, '@');
    expect(screen.getByTestId('mention-option-socrates')).toBeInTheDocument();
    expect(screen.getByTestId('mention-option-plato')).toBeInTheDocument();
  });
});

describe('MessageInput - styled mention overlay', () => {
  it('shows styled mention overlay when thinker name is in message', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');
    await user.click(screen.getByTestId('mention-option-socrates'));

    // Overlay should appear with styled mention
    expect(screen.getByTestId('mention-overlay')).toBeInTheDocument();
  });

  it('does not show overlay when no mentions in text', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello world');

    // No overlay since no thinker names match
    expect(screen.queryByTestId('mention-overlay')).not.toBeInTheDocument();
  });

  it('overlay contains the thinker name text', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello @');
    await user.click(screen.getByTestId('mention-option-plato'));

    const overlay = screen.getByTestId('mention-overlay');
    expect(overlay.textContent).toContain('Plato');
  });

  it('clears overlay when message is sent', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');
    await user.click(screen.getByTestId('mention-option-socrates'));
    expect(screen.getByTestId('mention-overlay')).toBeInTheDocument();

    // Send the message
    await user.click(screen.getByTestId('send-button'));

    // Overlay should be gone
    expect(screen.queryByTestId('mention-overlay')).not.toBeInTheDocument();
  });

  it('makes textarea text transparent when overlay is visible', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} thinkers={mockThinkers} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '@');
    await user.click(screen.getByTestId('mention-option-socrates'));

    // Textarea should have transparent text class when overlay is visible
    expect(textarea).toHaveClass('text-transparent');
  });
});
