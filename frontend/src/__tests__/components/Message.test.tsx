import { render, screen } from '@testing-library/react';
import { Message } from '@/components/Message';
import type { Message as MessageType } from '@/types';

const createMessage = (overrides: Partial<MessageType> = {}): MessageType => ({
  id: 'msg-1',
  conversation_id: 'conv-1',
  sender_type: 'user',
  sender_name: null,
  content: 'Hello, world!',
  cost: null,
  created_at: '2024-01-15T10:30:00Z',
  ...overrides,
});

describe('Message', () => {
  it('renders user message', () => {
    const message = createMessage({ sender_type: 'user' });
    render(<Message message={message} />);

    expect(screen.getByTestId('message')).toBeInTheDocument();
    expect(screen.getByText('Hello, world!')).toBeInTheDocument();
    expect(screen.getByTestId('message')).toHaveAttribute(
      'data-sender-type',
      'user'
    );
  });

  it('renders thinker message with name', () => {
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
    });
    render(<Message message={message} />);

    expect(screen.getByTestId('message')).toHaveAttribute(
      'data-sender-type',
      'thinker'
    );
    expect(screen.getByTestId('thinker-name')).toHaveTextContent('Socrates');
  });

  it('renders system message', () => {
    const message = createMessage({
      sender_type: 'system',
      content: 'User joined the chat',
    });
    render(<Message message={message} />);

    expect(screen.getByTestId('message')).toHaveAttribute(
      'data-sender-type',
      'system'
    );
    expect(screen.getByText('User joined the chat')).toBeInTheDocument();
  });

  it('displays cost when present', () => {
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
      cost: 0.0025,
    });
    render(<Message message={message} />);

    expect(screen.getByText('$0.0025')).toBeInTheDocument();
  });

  it('does not display cost when null', () => {
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
      cost: null,
    });
    render(<Message message={message} />);

    expect(screen.queryByText(/\$\d/)).not.toBeInTheDocument();
  });

  it('applies custom thinker color', () => {
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
    });
    render(<Message message={message} thinkerColor="#FF0000" />);

    const nameElement = screen.getByTestId('thinker-name');
    expect(nameElement).toHaveStyle({ color: '#FF0000' });
  });

  it('formats timestamp correctly', () => {
    const message = createMessage({
      created_at: '2024-01-15T10:30:00Z',
    });
    render(<Message message={message} />);

    // Time format depends on locale, so we just check it's there
    expect(screen.getByText(/\d{1,2}:\d{2}/)).toBeInTheDocument();
  });
});
