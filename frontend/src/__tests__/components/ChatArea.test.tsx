import { render, screen, fireEvent } from '@/test-utils';
import { ChatArea } from '@/components/ChatArea';
import type { Conversation, Message } from '@/types';

const createConversation = (): Conversation => ({
  id: 'conv-1',
  session_id: 'session-1',
  topic: 'Philosophy of Mind',
  thinkers: [
    {
      id: 'thinker-1',
      name: 'Socrates',
      bio: 'Ancient philosopher',
      positions: 'Socratic method',
      style: 'Questions everything',
      color: '#3B82F6',
    },
  ],
  messages: [],
  total_cost: 0,
  created_at: '2024-01-15T10:00:00Z',
  updated_at: new Date().toISOString(),
});

const createMessage = (id: string, content: string): Message => ({
  id,
  conversation_id: 'conv-1',
  sender_type: 'user',
  sender_name: null,
  content,
  cost: null,
  created_at: new Date().toISOString(),
});

describe('ChatArea', () => {
  const defaultProps = {
    conversation: null as Conversation | null,
    messages: [] as Message[],
    typingThinkers: [] as string[],
    onSendMessage: jest.fn(),
    isConnected: true,
  };

  it('renders empty state when no conversation', () => {
    render(<ChatArea {...defaultProps} />);
    expect(screen.getByTestId('chat-area-empty')).toBeInTheDocument();
    expect(
      screen.getByText('Welcome to dining philosophers!')
    ).toBeInTheDocument();
  });

  it('renders chat area when conversation is selected', () => {
    const conversation = createConversation();
    render(<ChatArea {...defaultProps} conversation={conversation} />);

    expect(screen.getByTestId('chat-area')).toBeInTheDocument();
    expect(screen.getByText('Philosophy of Mind')).toBeInTheDocument();
    expect(screen.getByText('with Socrates')).toBeInTheDocument();
  });

  it('renders messages', () => {
    const conversation = createConversation();
    const messages = [createMessage('1', 'Hello'), createMessage('2', 'World')];
    render(
      <ChatArea
        {...defaultProps}
        conversation={conversation}
        messages={messages}
      />
    );

    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('World')).toBeInTheDocument();
  });

  it('renders typing indicator', () => {
    const conversation = createConversation();
    render(
      <ChatArea
        {...defaultProps}
        conversation={conversation}
        typingThinkers={['Socrates']}
      />
    );

    expect(screen.getByTestId('thinker-typing-indicator')).toBeInTheDocument();
    expect(screen.getByText('Thinking...')).toBeInTheDocument();
    expect(screen.getByText('Socrates')).toBeInTheDocument();
  });

  it('renders message input', () => {
    const conversation = createConversation();
    render(<ChatArea {...defaultProps} conversation={conversation} />);

    expect(screen.getByTestId('message-input')).toBeInTheDocument();
  });

  it('shows reconnecting status when disconnected', () => {
    const conversation = createConversation();
    render(
      <ChatArea
        {...defaultProps}
        conversation={conversation}
        isConnected={false}
      />
    );

    expect(screen.getByTestId('connection-status')).toBeInTheDocument();
    expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
  });

  it('disables input when disconnected', () => {
    const conversation = createConversation();
    render(
      <ChatArea
        {...defaultProps}
        conversation={conversation}
        isConnected={false}
      />
    );

    expect(screen.getByTestId('message-textarea')).toBeDisabled();
  });

  it('renders error banner when error message is provided', () => {
    const conversation = createConversation();
    render(
      <ChatArea
        {...defaultProps}
        conversation={conversation}
        errorMessage="Test error message"
      />
    );

    expect(screen.getByTestId('error-banner')).toBeInTheDocument();
    expect(screen.getByText('Test error message')).toBeInTheDocument();
  });

  it('does not render error banner when error message is empty', () => {
    const conversation = createConversation();
    render(
      <ChatArea {...defaultProps} conversation={conversation} errorMessage="" />
    );

    expect(screen.queryByTestId('error-banner')).not.toBeInTheDocument();
  });

  it('renders billing error message in error banner', () => {
    const conversation = createConversation();
    const billingError =
      'Spend limit reached ($10.00/$10.00). Contact admin to increase your limit.';
    render(
      <ChatArea
        {...defaultProps}
        conversation={conversation}
        errorMessage={billingError}
      />
    );

    expect(screen.getByTestId('error-banner')).toBeInTheDocument();
    expect(screen.getByText(billingError)).toBeInTheDocument();
  });

  it('renders hamburger menu button in header when onSidebarToggle is provided', () => {
    const conversation = createConversation();
    const onSidebarToggle = jest.fn();
    render(
      <ChatArea
        {...defaultProps}
        conversation={conversation}
        onSidebarToggle={onSidebarToggle}
        sidebarOpen={false}
      />
    );

    expect(screen.getByTestId('sidebar-toggle')).toBeInTheDocument();
  });

  it('calls onSidebarToggle when hamburger button is clicked', () => {
    const conversation = createConversation();
    const onSidebarToggle = jest.fn();
    render(
      <ChatArea
        {...defaultProps}
        conversation={conversation}
        onSidebarToggle={onSidebarToggle}
        sidebarOpen={false}
      />
    );

    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(onSidebarToggle).toHaveBeenCalled();
  });

  it('does not render hamburger button when onSidebarToggle is not provided', () => {
    const conversation = createConversation();
    render(<ChatArea {...defaultProps} conversation={conversation} />);

    expect(screen.queryByTestId('sidebar-toggle')).not.toBeInTheDocument();
  });

  describe('Speed Control', () => {
    it('renders speed control when onSpeedChange is provided', () => {
      const conversation = createConversation();
      const onSpeedChange = jest.fn();
      render(
        <ChatArea
          {...defaultProps}
          conversation={conversation}
          onSpeedChange={onSpeedChange}
        />
      );

      expect(screen.getByTestId('speed-control')).toBeInTheDocument();
      expect(screen.getByTestId('speed-slider')).toBeInTheDocument();
    });

    it('does not render speed control when onSpeedChange is not provided', () => {
      const conversation = createConversation();
      render(<ChatArea {...defaultProps} conversation={conversation} />);

      expect(screen.queryByTestId('speed-control')).not.toBeInTheDocument();
    });

    it('renders equally-spaced extreme labels (Fast and Contemplative)', () => {
      const conversation = createConversation();
      const onSpeedChange = jest.fn();
      render(
        <ChatArea
          {...defaultProps}
          conversation={conversation}
          onSpeedChange={onSpeedChange}
        />
      );

      expect(screen.getByTestId('speed-label-min')).toHaveTextContent('Fast');
      expect(screen.getByTestId('speed-label-max')).toHaveTextContent(
        'Contemplative'
      );
    });

    it('displays current pace value below slider', () => {
      const conversation = createConversation();
      const onSpeedChange = jest.fn();
      render(
        <ChatArea
          {...defaultProps}
          conversation={conversation}
          onSpeedChange={onSpeedChange}
          speedMultiplier={1.0}
        />
      );

      const currentValue = screen.getByTestId('speed-current-value');
      expect(currentValue).toBeInTheDocument();
      expect(currentValue).toHaveTextContent('Pace:');
      expect(currentValue).toHaveTextContent('Normal');
    });

    it('calls onSpeedChange when slider value changes', () => {
      const conversation = createConversation();
      const onSpeedChange = jest.fn();
      render(
        <ChatArea
          {...defaultProps}
          conversation={conversation}
          onSpeedChange={onSpeedChange}
          speedMultiplier={1.0}
        />
      );

      const slider = screen.getByTestId('speed-slider');
      fireEvent.change(slider, { target: { value: '2.0' } });
      expect(onSpeedChange).toHaveBeenCalledWith(2.0);
    });

    it('shows correct speed label for different multiplier values', () => {
      const conversation = createConversation();
      const onSpeedChange = jest.fn();

      // Test with Fast (0.5)
      const { rerender } = render(
        <ChatArea
          {...defaultProps}
          conversation={conversation}
          onSpeedChange={onSpeedChange}
          speedMultiplier={0.5}
        />
      );
      expect(screen.getByTestId('speed-current-value')).toHaveTextContent(
        'Fast'
      );

      // Test with Contemplative (6.0)
      rerender(
        <ChatArea
          {...defaultProps}
          conversation={conversation}
          onSpeedChange={onSpeedChange}
          speedMultiplier={6.0}
        />
      );
      expect(screen.getByTestId('speed-current-value')).toHaveTextContent(
        'Contemplative'
      );
    });

    it('has correct slider attributes (min, max, step)', () => {
      const conversation = createConversation();
      const onSpeedChange = jest.fn();
      render(
        <ChatArea
          {...defaultProps}
          conversation={conversation}
          onSpeedChange={onSpeedChange}
        />
      );

      const slider = screen.getByTestId('speed-slider');
      expect(slider).toHaveAttribute('min', '0.5');
      expect(slider).toHaveAttribute('max', '6');
      expect(slider).toHaveAttribute('step', '0.5');
    });
  });
});
