import { render, screen, fireEvent } from '@/test-utils';
import { Message } from '@/components/Message';
import type { Message as MessageType, ConversationThinker } from '@/types';

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

const createThinker = (
  name: string,
  overrides: Partial<ConversationThinker> = {}
): ConversationThinker => ({
  id: `thinker-${name.toLowerCase().replace(' ', '-')}`,
  name,
  bio: `Bio of ${name}`,
  positions: `Positions of ${name}`,
  style: `Style of ${name}`,
  color: '#3B82F6',
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

  it('renders thinker avatar alongside thinker message', () => {
    const thinker = createThinker('Socrates');
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
    });
    render(<Message message={message} thinker={thinker} />);

    // Avatar should show initials 'S' for Socrates
    expect(screen.getByTitle('Socrates')).toBeInTheDocument();
  });

  it('does not show thinker avatar for user messages', () => {
    const thinker = createThinker('Socrates');
    const message = createMessage({ sender_type: 'user', content: 'Hello' });
    render(<Message message={message} thinker={thinker} />);

    expect(screen.queryByTitle('Socrates')).not.toBeInTheDocument();
  });
});

describe('Message mention highlighting', () => {
  it('renders plain text when no thinkers provided', () => {
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
      content: 'Hello Plato, what do you think?',
    });
    render(<Message message={message} allThinkers={[]} />);
    expect(
      screen.getByText('Hello Plato, what do you think?')
    ).toBeInTheDocument();
  });

  it('highlights a thinker mention in message content', () => {
    const thinkers = [createThinker('Plato')];
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
      content: 'Hello Plato, what do you think?',
    });
    render(<Message message={message} allThinkers={thinkers} />);

    // The mention "Plato" should be highlighted in a span
    const mentions = screen.getAllByText('Plato');
    // One from thinker header (sender_name), at least one from mention highlight
    expect(mentions.length).toBeGreaterThanOrEqual(1);
  });

  it('handles message with no mentions (no allThinkers match)', () => {
    const thinkers = [createThinker('Einstein')];
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
      content: 'The unexamined life is not worth living.',
    });
    render(<Message message={message} allThinkers={thinkers} />);
    expect(
      screen.getByText('The unexamined life is not worth living.')
    ).toBeInTheDocument();
  });

  it('highlights multiple different thinkers in same message', () => {
    const thinkers = [createThinker('Plato'), createThinker('Aristotle')];
    const message = createMessage({
      sender_type: 'thinker',
      sender_name: 'Socrates',
      content: 'Plato and Aristotle disagree on this.',
    });
    render(<Message message={message} allThinkers={thinkers} />);

    // Both names should appear in the rendered output
    expect(screen.getAllByText('Plato').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Aristotle').length).toBeGreaterThanOrEqual(1);
  });

  it('matches partial name (first name only)', () => {
    const thinkers = [createThinker('Karl Marx')];
    const message = createMessage({
      sender_type: 'user',
      content: 'What would Karl say about this?',
    });
    render(<Message message={message} allThinkers={thinkers} />);

    // "Karl" should match as part of "Karl Marx" (words > 2 chars are indexed)
    const karlMatches = screen.queryAllByText('Karl');
    expect(karlMatches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders user message with thinker mentions', () => {
    const thinkers = [createThinker('Socrates')];
    const message = createMessage({
      sender_type: 'user',
      content: 'Socrates, please respond.',
    });
    render(<Message message={message} allThinkers={thinkers} />);

    // Message renders correctly with mentions
    expect(screen.getByTestId('message')).toHaveAttribute(
      'data-sender-type',
      'user'
    );
  });

  it('renders plain text when allThinkers is empty array', () => {
    const message = createMessage({
      sender_type: 'user',
      content: 'Hello everyone!',
    });
    render(<Message message={message} allThinkers={[]} />);
    expect(screen.getByText('Hello everyone!')).toBeInTheDocument();
  });
});
