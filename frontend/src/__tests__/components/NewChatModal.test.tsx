import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NewChatModal } from '@/components/NewChatModal';
import type { ThinkerProfile, ThinkerSuggestion } from '@/types';

const createSuggestion = (name: string): ThinkerSuggestion => ({
  name,
  reason: `${name} would be great`,
  profile: {
    name,
    bio: `Bio of ${name}`,
    positions: 'Some positions',
    style: 'Some style',
  },
});

describe('NewChatModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: jest.fn(),
    onCreate: jest.fn().mockResolvedValue(undefined),
    onSuggestThinkers: jest
      .fn()
      .mockResolvedValue([createSuggestion('Socrates')]),
    onValidateThinker: jest.fn().mockResolvedValue({
      name: 'Custom',
      bio: 'Bio',
      positions: 'Positions',
      style: 'Style',
    } as ThinkerProfile),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders when open', () => {
    render(<NewChatModal {...defaultProps} />);
    expect(screen.getByTestId('new-chat-modal')).toBeInTheDocument();
    expect(screen.getByText('New Conversation')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(<NewChatModal {...defaultProps} isOpen={false} />);
    expect(screen.queryByTestId('new-chat-modal')).not.toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = jest.fn();
    render(<NewChatModal {...defaultProps} onClose={onClose} />);

    fireEvent.click(screen.getByLabelText('Close modal'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when clicking outside modal', () => {
    const onClose = jest.fn();
    render(<NewChatModal {...defaultProps} onClose={onClose} />);

    fireEvent.click(screen.getByTestId('new-chat-modal'));
    expect(onClose).toHaveBeenCalled();
  });

  it('renders topic input on first step', () => {
    render(<NewChatModal {...defaultProps} />);
    expect(screen.getByTestId('topic-input')).toBeInTheDocument();
    expect(
      screen.getByText('What would you like to discuss?')
    ).toBeInTheDocument();
  });

  it('proceeds to thinker selection after entering topic', async () => {
    const user = userEvent.setup();
    const onSuggestThinkers = jest
      .fn()
      .mockResolvedValue([createSuggestion('Socrates')]);

    render(
      <NewChatModal {...defaultProps} onSuggestThinkers={onSuggestThinkers} />
    );

    const input = screen.getByTestId('topic-input');
    await user.type(input, 'Philosophy of mind');
    await user.click(screen.getByTestId('next-button'));

    await waitFor(() => {
      expect(onSuggestThinkers).toHaveBeenCalledWith('Philosophy of mind', 5);
    });

    await waitFor(() => {
      expect(screen.getByText('Select Thinkers')).toBeInTheDocument();
    });
  });

  it('disables next button when topic is empty', () => {
    render(<NewChatModal {...defaultProps} />);
    expect(screen.getByTestId('next-button')).toBeDisabled();
  });

  it('shows back button on thinker selection step', async () => {
    const user = userEvent.setup();
    render(<NewChatModal {...defaultProps} />);

    await user.type(screen.getByTestId('topic-input'), 'Topic');
    await user.click(screen.getByTestId('next-button'));

    await waitFor(() => {
      expect(screen.getByText('Back')).toBeInTheDocument();
    });
  });

  it('goes back to topic step when back button is clicked', async () => {
    const user = userEvent.setup();
    render(<NewChatModal {...defaultProps} />);

    await user.type(screen.getByTestId('topic-input'), 'Topic');
    await user.click(screen.getByTestId('next-button'));

    await waitFor(() => {
      expect(screen.getByText('Back')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Back'));

    await waitFor(() => {
      expect(screen.getByTestId('topic-input')).toBeInTheDocument();
    });
  });

  it('creates conversation when thinkers are selected', async () => {
    const user = userEvent.setup();
    const onCreate = jest.fn().mockResolvedValue(undefined);

    render(<NewChatModal {...defaultProps} onCreate={onCreate} />);

    // Enter topic
    await user.type(screen.getByTestId('topic-input'), 'Philosophy');
    await user.click(screen.getByTestId('next-button'));

    // Wait for suggestions and click the accept button
    await waitFor(() => {
      expect(screen.getByTestId('thinker-suggestion')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('accept-suggestion'));

    // Create conversation
    await user.click(screen.getByTestId('create-button'));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith('Philosophy', [
        {
          name: 'Socrates',
          bio: 'Bio of Socrates',
          positions: 'Some positions',
          style: 'Some style',
        },
      ]);
    });
  });

  it('disables create button when no thinkers selected', async () => {
    const user = userEvent.setup();
    render(<NewChatModal {...defaultProps} />);

    await user.type(screen.getByTestId('topic-input'), 'Philosophy');
    await user.click(screen.getByTestId('next-button'));

    await waitFor(() => {
      expect(screen.getByTestId('create-button')).toBeDisabled();
    });
  });

  it('proceeds to thinker selection even when suggestion API fails', async () => {
    const user = userEvent.setup();
    const onSuggestThinkers = jest
      .fn()
      .mockRejectedValue(new Error('API credit limit reached'));

    render(
      <NewChatModal {...defaultProps} onSuggestThinkers={onSuggestThinkers} />
    );

    await user.type(screen.getByTestId('topic-input'), 'Philosophy');
    await user.click(screen.getByTestId('next-button'));

    // Should still proceed to thinker selection step
    await waitFor(() => {
      expect(screen.getByText('Select Thinkers')).toBeInTheDocument();
    });

    // Should show the error message
    await waitFor(() => {
      expect(screen.getByText('API credit limit reached')).toBeInTheDocument();
    });
  });
});
