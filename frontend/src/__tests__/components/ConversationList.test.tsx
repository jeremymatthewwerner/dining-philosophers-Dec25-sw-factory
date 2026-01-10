import { fireEvent, render, screen } from '@/test-utils';
import { ConversationList } from '@/components/ConversationList';
import type { ConversationSummary } from '@/types';

const createConversation = (
  id: string,
  topic: string
): ConversationSummary => ({
  id,
  topic,
  thinker_names: ['Socrates', 'Plato'],
  thinkers: [
    { name: 'Socrates', image_url: null },
    { name: 'Plato', image_url: null },
  ],
  message_count: 10,
  total_cost: 0.05,
  created_at: '2024-01-15T10:00:00Z',
  updated_at: new Date().toISOString(),
});

describe('ConversationList', () => {
  it('renders empty state when no conversations', () => {
    render(
      <ConversationList
        conversations={[]}
        selectedId={null}
        onSelect={jest.fn()}
      />
    );
    expect(screen.getByTestId('conversation-list-empty')).toBeInTheDocument();
    expect(screen.getByText(/No conversations yet/)).toBeInTheDocument();
  });

  it('renders conversation items', () => {
    const conversations = [
      createConversation('1', 'Philosophy'),
      createConversation('2', 'Science'),
    ];
    render(
      <ConversationList
        conversations={conversations}
        selectedId={null}
        onSelect={jest.fn()}
      />
    );

    expect(screen.getByTestId('conversation-list')).toBeInTheDocument();
    // ScrollingText renders text in two spans (hidden measurement + visible)
    expect(screen.getAllByText('Philosophy').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Science').length).toBeGreaterThanOrEqual(1);
  });

  it('shows thinker avatars', () => {
    const conversations = [createConversation('1', 'Philosophy')];
    render(
      <ConversationList
        conversations={conversations}
        selectedId={null}
        onSelect={jest.fn()}
      />
    );

    // Avatars have the thinker name as title
    expect(screen.getByTitle('Socrates')).toBeInTheDocument();
    expect(screen.getByTitle('Plato')).toBeInTheDocument();
  });

  it('shows message count', () => {
    const conversations = [createConversation('1', 'Philosophy')];
    render(
      <ConversationList
        conversations={conversations}
        selectedId={null}
        onSelect={jest.fn()}
      />
    );

    expect(screen.getByText('10 thinker messages')).toBeInTheDocument();
  });

  it('shows total cost', () => {
    const conversations = [createConversation('1', 'Philosophy')];
    render(
      <ConversationList
        conversations={conversations}
        selectedId={null}
        onSelect={jest.fn()}
      />
    );

    expect(screen.getByText('$0.050')).toBeInTheDocument();
  });

  it('calls onSelect when conversation is clicked', () => {
    const onSelect = jest.fn();
    const conversations = [createConversation('1', 'Philosophy')];
    render(
      <ConversationList
        conversations={conversations}
        selectedId={null}
        onSelect={onSelect}
      />
    );

    // Click on the conversation item directly using testid
    fireEvent.click(screen.getByTestId('conversation-item'));
    expect(onSelect).toHaveBeenCalledWith('1');
  });

  it('highlights selected conversation', () => {
    const conversations = [
      createConversation('1', 'Philosophy'),
      createConversation('2', 'Science'),
    ];
    render(
      <ConversationList
        conversations={conversations}
        selectedId="1"
        onSelect={jest.fn()}
      />
    );

    const items = screen.getAllByTestId('conversation-item');
    expect(items[0]).toHaveAttribute('data-selected', 'true');
    expect(items[1]).toHaveAttribute('data-selected', 'false');
  });

  it('calls onDelete when delete button is clicked', () => {
    const onDelete = jest.fn();
    const conversations = [createConversation('1', 'Philosophy')];
    render(
      <ConversationList
        conversations={conversations}
        selectedId={null}
        onSelect={jest.fn()}
        onDelete={onDelete}
      />
    );

    fireEvent.click(screen.getByTestId('delete-conversation'));
    expect(onDelete).toHaveBeenCalledWith('1');
  });
});
