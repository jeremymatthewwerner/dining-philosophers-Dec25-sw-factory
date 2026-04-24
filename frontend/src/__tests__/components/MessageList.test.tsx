import { render, screen, createMessage } from '@/test-utils';
import { MessageList } from '@/components/MessageList';
import type { ConversationThinker } from '@/types';

const thinkers: ConversationThinker[] = [
  {
    id: 'thinker-1',
    name: 'Socrates',
    bio: 'Ancient philosopher',
    positions: 'Socratic method',
    style: 'Questions everything',
    color: '#3B82F6',
    image_url: null,
  },
];

describe('MessageList', () => {
  it('renders empty state when no messages', () => {
    render(<MessageList messages={[]} thinkers={thinkers} />);
    expect(screen.getByTestId('message-list-empty')).toBeInTheDocument();
    expect(screen.getByText(/No messages yet/)).toBeInTheDocument();
  });

  it('renders messages', () => {
    const messages = [
      createMessage({ id: '1', content: 'Hello' }),
      createMessage({ id: '2', content: 'World' }),
    ];
    render(<MessageList messages={messages} thinkers={thinkers} />);

    expect(screen.getByTestId('message-list')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('World')).toBeInTheDocument();
  });

  it('renders user and thinker messages', () => {
    const messages = [
      createMessage({ id: '1', content: 'User question', sender_type: 'user' }),
      createMessage({
        id: '2',
        content: 'Thinker response',
        sender_type: 'thinker',
        sender_name: 'Socrates',
      }),
    ];
    render(<MessageList messages={messages} thinkers={thinkers} />);

    const messageElements = screen.getAllByTestId('message');
    expect(messageElements).toHaveLength(2);
    expect(messageElements[0]).toHaveAttribute('data-sender-type', 'user');
    expect(messageElements[1]).toHaveAttribute('data-sender-type', 'thinker');
  });

  it('passes thinker color to messages', () => {
    const messages = [
      createMessage({
        id: '1',
        content: 'Response',
        sender_type: 'thinker',
        sender_name: 'Socrates',
      }),
    ];
    render(<MessageList messages={messages} thinkers={thinkers} />);

    const thinkerName = screen.getByTestId('thinker-name');
    expect(thinkerName).toHaveStyle({ color: '#3B82F6' });
  });
});
