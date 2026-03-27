import {
  fireEvent,
  render,
  screen,
  createConversationSummary,
} from '@/test-utils';
import { ConversationList } from '@/components/ConversationList';

// Use createConversationSummary from test-utils to eliminate the local helper
// that previously duplicated the ConversationSummary factory pattern.

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
      createConversationSummary({ id: '1', topic: 'Philosophy' }),
      createConversationSummary({ id: '2', topic: 'Science' }),
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
    // Override thinkers to have two specific entries with known names
    const conversations = [
      createConversationSummary({
        id: '1',
        topic: 'Philosophy',
        thinker_names: ['Socrates', 'Plato'],
        thinkers: [
          { name: 'Socrates', image_url: null },
          { name: 'Plato', image_url: null },
        ],
      }),
    ];
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
    const conversations = [
      createConversationSummary({
        id: '1',
        topic: 'Philosophy',
        message_count: 10,
      }),
    ];
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
    const conversations = [
      createConversationSummary({
        id: '1',
        topic: 'Philosophy',
        total_cost: 0.05,
      }),
    ];
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
    const conversations = [
      createConversationSummary({ id: '1', topic: 'Philosophy' }),
    ];
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
      createConversationSummary({ id: '1', topic: 'Philosophy' }),
      createConversationSummary({ id: '2', topic: 'Science' }),
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
    const conversations = [
      createConversationSummary({ id: '1', topic: 'Philosophy' }),
    ];
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
