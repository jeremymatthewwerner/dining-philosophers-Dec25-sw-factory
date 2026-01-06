import { fireEvent, render, screen, waitFor } from '@/test-utils';
import { FeedbackModal } from '@/components/FeedbackModal';
import * as api from '@/lib/api';

// Mock the API
jest.mock('@/lib/api', () => ({
  ...jest.requireActual('@/lib/api'),
  submitFeedback: jest.fn(),
}));

const mockSubmitFeedback = api.submitFeedback as jest.MockedFunction<
  typeof api.submitFeedback
>;

describe('FeedbackModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockSubmitFeedback.mockResolvedValue({
      id: 'feedback-123',
      message: 'Thank you!',
    });
  });

  it('renders modal when open', () => {
    render(<FeedbackModal {...defaultProps} />);
    expect(screen.getByTestId('feedback-modal')).toBeInTheDocument();
    expect(screen.getByText('Send Feedback')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(<FeedbackModal {...defaultProps} isOpen={false} />);
    expect(screen.queryByTestId('feedback-modal')).not.toBeInTheDocument();
  });

  it('renders feedback type buttons', () => {
    render(<FeedbackModal {...defaultProps} />);
    expect(screen.getByTestId('feedback-type-bug')).toBeInTheDocument();
    expect(screen.getByTestId('feedback-type-feature')).toBeInTheDocument();
    expect(screen.getByTestId('feedback-type-other')).toBeInTheDocument();
  });

  it('renders message textarea', () => {
    render(<FeedbackModal {...defaultProps} />);
    expect(screen.getByTestId('feedback-message')).toBeInTheDocument();
  });

  it('renders optional name and email fields', () => {
    render(<FeedbackModal {...defaultProps} />);
    expect(screen.getByTestId('feedback-name')).toBeInTheDocument();
    expect(screen.getByTestId('feedback-email')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = jest.fn();
    render(<FeedbackModal {...defaultProps} onClose={onClose} />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when cancel button is clicked', () => {
    const onClose = jest.fn();
    render(<FeedbackModal {...defaultProps} onClose={onClose} />);

    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when clicking outside modal', () => {
    const onClose = jest.fn();
    render(<FeedbackModal {...defaultProps} onClose={onClose} />);

    // Click on the backdrop (data-testid="feedback-modal" is the backdrop)
    const modal = screen.getByTestId('feedback-modal');
    fireEvent.click(modal);
    expect(onClose).toHaveBeenCalled();
  });

  it('submit button is disabled when message is empty', () => {
    render(<FeedbackModal {...defaultProps} />);
    const submitButton = screen.getByTestId('submit-feedback');
    expect(submitButton).toBeDisabled();
  });

  it('submit button is enabled when message has content', () => {
    render(<FeedbackModal {...defaultProps} />);

    const textarea = screen.getByTestId('feedback-message');
    fireEvent.change(textarea, {
      target: { value: 'This is a test feedback message' },
    });

    const submitButton = screen.getByTestId('submit-feedback');
    expect(submitButton).not.toBeDisabled();
  });

  it('changes feedback type when type button is clicked', () => {
    render(<FeedbackModal {...defaultProps} />);

    // Bug is selected by default
    const bugButton = screen.getByTestId('feedback-type-bug');
    expect(bugButton).toHaveClass('bg-blue-600');

    // Click feature button
    const featureButton = screen.getByTestId('feedback-type-feature');
    fireEvent.click(featureButton);

    // Feature should now be selected
    expect(featureButton).toHaveClass('bg-blue-600');
    expect(bugButton).not.toHaveClass('bg-blue-600');
  });

  it('submits feedback successfully', async () => {
    const onClose = jest.fn();
    render(<FeedbackModal {...defaultProps} onClose={onClose} />);

    // Fill in the form
    fireEvent.change(screen.getByTestId('feedback-message'), {
      target: { value: 'This is a test bug report for testing.' },
    });
    fireEvent.change(screen.getByTestId('feedback-name'), {
      target: { value: 'Test User' },
    });
    fireEvent.change(screen.getByTestId('feedback-email'), {
      target: { value: 'test@example.com' },
    });

    // Submit
    fireEvent.click(screen.getByTestId('submit-feedback'));

    // Wait for success state
    await waitFor(() => {
      expect(screen.getByText('Thank you!')).toBeInTheDocument();
    });

    expect(mockSubmitFeedback).toHaveBeenCalledWith({
      feedback_type: 'bug',
      message: 'This is a test bug report for testing.',
      name: 'Test User',
      email: 'test@example.com',
      user_agent: expect.any(String),
    });
  });

  it('shows success message after submission', async () => {
    render(<FeedbackModal {...defaultProps} />);

    fireEvent.change(screen.getByTestId('feedback-message'), {
      target: { value: 'This is a test feedback message.' },
    });
    fireEvent.click(screen.getByTestId('submit-feedback'));

    await waitFor(() => {
      expect(screen.getByText('Thank you!')).toBeInTheDocument();
      expect(
        screen.getByText(/Your feedback has been submitted successfully/)
      ).toBeInTheDocument();
    });
  });

  it('shows error message on submission failure', async () => {
    mockSubmitFeedback.mockRejectedValue(new Error('Network error'));

    render(<FeedbackModal {...defaultProps} />);

    fireEvent.change(screen.getByTestId('feedback-message'), {
      target: { value: 'This is a test feedback message.' },
    });
    fireEvent.click(screen.getByTestId('submit-feedback'));

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('shows error for message too short', async () => {
    render(<FeedbackModal {...defaultProps} />);

    fireEvent.change(screen.getByTestId('feedback-message'), {
      target: { value: 'Short' },
    });
    fireEvent.click(screen.getByTestId('submit-feedback'));

    await waitFor(() => {
      expect(
        screen.getByText('Message must be at least 10 characters')
      ).toBeInTheDocument();
    });
  });

  it('closes modal after clicking Done on success screen', async () => {
    const onClose = jest.fn();
    render(<FeedbackModal {...defaultProps} onClose={onClose} />);

    fireEvent.change(screen.getByTestId('feedback-message'), {
      target: { value: 'This is a test feedback message.' },
    });
    fireEvent.click(screen.getByTestId('submit-feedback'));

    await waitFor(() => {
      expect(screen.getByText('Thank you!')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Done'));
    expect(onClose).toHaveBeenCalled();
  });
});
