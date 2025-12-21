import { render, screen } from '@testing-library/react';
import { MessageList } from '@/components/MessageList';
import type { ConversationThinker, Message } from '@/types';

const createMessage = (
  id: string,
  content: string,
  sender_type: Message['sender_type'] = 'user'
): Message => ({
  id,
  conversation_id: 'conv-1',
  sender_type,
  sender_name: sender_type === 'thinker' ? 'Socrates' : null,
  content,
  cost: null,
  created_at: new Date().toISOString(),
});

const thinkers: ConversationThinker[] = [
  {
    id: 'thinker-1',
    name: 'Socrates',
    bio: 'Ancient philosopher',
    positions: 'Socratic method',
    style: 'Questions everything',
    color: '#3B82F6',
  },
];

describe('MessageList', () => {
  it('renders empty state when no messages', () => {
    render(<MessageList messages={[]} thinkers={thinkers} />);
    expect(screen.getByTestId('message-list-empty')).toBeInTheDocument();
    expect(screen.getByText(/No messages yet/)).toBeInTheDocument();
  });

  it('renders messages', () => {
    const messages = [createMessage('1', 'Hello'), createMessage('2', 'World')];
    render(<MessageList messages={messages} thinkers={thinkers} />);

    expect(screen.getByTestId('message-list')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('World')).toBeInTheDocument();
  });

  it('renders user and thinker messages', () => {
    const messages = [
      createMessage('1', 'User question', 'user'),
      createMessage('2', 'Thinker response', 'thinker'),
    ];
    render(<MessageList messages={messages} thinkers={thinkers} />);

    const messageElements = screen.getAllByTestId('message');
    expect(messageElements).toHaveLength(2);
    expect(messageElements[0]).toHaveAttribute('data-sender-type', 'user');
    expect(messageElements[1]).toHaveAttribute('data-sender-type', 'thinker');
  });

  it('passes thinker color to messages', () => {
    const messages = [createMessage('1', 'Response', 'thinker')];
    render(<MessageList messages={messages} thinkers={thinkers} />);

    const thinkerName = screen.getByTestId('thinker-name');
    expect(thinkerName).toHaveStyle({ color: '#3B82F6' });
  });
});
