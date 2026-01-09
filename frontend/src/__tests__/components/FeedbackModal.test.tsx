import { fireEvent, render, screen, waitFor } from '@/test-utils';
import { FeedbackModal } from '@/components/FeedbackModal';
import * as api from '@/lib/api';

// Mock the API
jest.mock('@/lib/api', () => ({
  ...jest.requireActual('@/lib/api'),
  submitFeedback: jest.fn(),
  getStoredUser: jest.fn(),
}));

const mockSubmitFeedback = api.submitFeedback as jest.MockedFunction<
  typeof api.submitFeedback
>;
const mockGetStoredUser = api.getStoredUser as jest.MockedFunction<
  typeof api.getStoredUser
>;

// Helper to create a mock file
const createMockFile = (name: string, size: number, type: string): File => {
  const content = new Array(size).fill('a').join('');
  return new File([content], name, { type });
};

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
    // Default to no user logged in
    mockGetStoredUser.mockReturnValue(null);
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
      username: undefined, // No user logged in
      user_agent: expect.any(String),
      screenshot_data: undefined,
      screenshot_filename: undefined,
    });
  });

  it('includes username when user is logged in', async () => {
    // Mock a logged-in user
    mockGetStoredUser.mockReturnValue({
      id: 'user-123',
      username: 'testuser123',
      display_name: 'Test User',
      is_admin: false,
      total_spend: 0,
      spend_limit: 100,
      language_preference: 'en',
      created_at: '2026-01-01T00:00:00Z',
    });

    render(<FeedbackModal {...defaultProps} />);

    fireEvent.change(screen.getByTestId('feedback-message'), {
      target: { value: 'This is feedback from a logged in user.' },
    });
    fireEvent.click(screen.getByTestId('submit-feedback'));

    await waitFor(() => {
      expect(screen.getByText('Thank you!')).toBeInTheDocument();
    });

    expect(mockSubmitFeedback).toHaveBeenCalledWith(
      expect.objectContaining({
        username: 'testuser123',
      })
    );
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

  it('does not auto-close modal after successful submission (user clicks Done)', async () => {
    jest.useFakeTimers();
    const onClose = jest.fn();
    render(<FeedbackModal {...defaultProps} onClose={onClose} />);

    fireEvent.change(screen.getByTestId('feedback-message'), {
      target: { value: 'This is a test feedback message.' },
    });
    fireEvent.click(screen.getByTestId('submit-feedback'));

    // Wait for success state
    await waitFor(() => {
      expect(screen.getByText('Thank you!')).toBeInTheDocument();
    });

    // Fast-forward 2 seconds - modal should NOT auto-close
    jest.advanceTimersByTime(2000);

    // onClose should not have been called automatically
    expect(onClose).not.toHaveBeenCalled();

    // User must click Done to close
    fireEvent.click(screen.getByText('Done'));
    expect(onClose).toHaveBeenCalledTimes(1);

    jest.useRealTimers();
  });

  it('renders screenshot upload input', () => {
    render(<FeedbackModal {...defaultProps} />);
    expect(screen.getByTestId('screenshot-input')).toBeInTheDocument();
    expect(screen.getByText(/Screenshot/)).toBeInTheDocument();
    expect(screen.getByText(/Max 5MB/)).toBeInTheDocument();
  });

  it('shows error for invalid file type', async () => {
    render(<FeedbackModal {...defaultProps} />);

    const input = screen.getByTestId('screenshot-input');
    const file = createMockFile('test.pdf', 1000, 'application/pdf');

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId('feedback-error')).toHaveTextContent(
        'Please upload an image file'
      );
    });
  });

  it('shows error for file too large', async () => {
    render(<FeedbackModal {...defaultProps} />);

    const input = screen.getByTestId('screenshot-input');
    // Create a file larger than 5MB
    const file = createMockFile('large.png', 6 * 1024 * 1024, 'image/png');

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId('feedback-error')).toHaveTextContent(
        'Screenshot must be less than 5MB'
      );
    });
  });

  it('displays uploaded file name and remove button', async () => {
    render(<FeedbackModal {...defaultProps} />);

    const input = screen.getByTestId('screenshot-input');
    const file = createMockFile('screenshot.png', 1000, 'image/png');

    // Mock FileReader
    const mockFileReader = {
      readAsDataURL: jest.fn(),
      result: 'data:image/png;base64,dGVzdA==',
      onload: null as
        | ((this: FileReader, ev: ProgressEvent<FileReader>) => unknown)
        | null,
      onerror: null as
        | ((this: FileReader, ev: ProgressEvent<FileReader>) => unknown)
        | null,
    };
    jest
      .spyOn(window, 'FileReader')
      .mockImplementation(() => mockFileReader as unknown as FileReader);

    fireEvent.change(input, { target: { files: [file] } });

    // Trigger the onload callback
    if (mockFileReader.onload) {
      mockFileReader.onload.call(
        mockFileReader as unknown as FileReader,
        {} as ProgressEvent<FileReader>
      );
    }

    await waitFor(() => {
      expect(screen.getByText('screenshot.png')).toBeInTheDocument();
      expect(screen.getByTestId('remove-screenshot')).toBeInTheDocument();
    });
  });

  it('removes screenshot when remove button is clicked', async () => {
    render(<FeedbackModal {...defaultProps} />);

    const input = screen.getByTestId('screenshot-input');
    const file = createMockFile('screenshot.png', 1000, 'image/png');

    // Mock FileReader
    const mockFileReader = {
      readAsDataURL: jest.fn(),
      result: 'data:image/png;base64,dGVzdA==',
      onload: null as
        | ((this: FileReader, ev: ProgressEvent<FileReader>) => unknown)
        | null,
      onerror: null as
        | ((this: FileReader, ev: ProgressEvent<FileReader>) => unknown)
        | null,
    };
    jest
      .spyOn(window, 'FileReader')
      .mockImplementation(() => mockFileReader as unknown as FileReader);

    fireEvent.change(input, { target: { files: [file] } });

    // Trigger the onload callback
    if (mockFileReader.onload) {
      mockFileReader.onload.call(
        mockFileReader as unknown as FileReader,
        {} as ProgressEvent<FileReader>
      );
    }

    await waitFor(() => {
      expect(screen.getByText('screenshot.png')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('remove-screenshot'));

    await waitFor(() => {
      expect(screen.queryByText('screenshot.png')).not.toBeInTheDocument();
      expect(screen.getByTestId('screenshot-input')).toBeInTheDocument();
    });
  });

  it('shows user-friendly error for network failures', async () => {
    mockSubmitFeedback.mockRejectedValue(
      new Error(
        'Unable to connect to the server. Please check your internet connection and try again.'
      )
    );

    render(<FeedbackModal {...defaultProps} />);

    fireEvent.change(screen.getByTestId('feedback-message'), {
      target: { value: 'This is a test feedback message.' },
    });
    fireEvent.click(screen.getByTestId('submit-feedback'));

    await waitFor(() => {
      expect(screen.getByTestId('feedback-error')).toHaveTextContent(
        'Unable to connect to the server'
      );
    });
  });
});
