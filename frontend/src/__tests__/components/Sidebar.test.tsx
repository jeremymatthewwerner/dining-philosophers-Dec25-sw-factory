import { fireEvent, render, screen } from '@testing-library/react';
import { Sidebar } from '@/components/Sidebar';
import type { ConversationSummary } from '@/types';

const createConversation = (
  id: string,
  topic: string
): ConversationSummary => ({
  id,
  topic,
  thinker_names: ['Socrates'],
  thinkers: [{ name: 'Socrates', image_url: null }],
  message_count: 5,
  total_cost: 0.01,
  created_at: '2024-01-15T10:00:00Z',
  updated_at: new Date().toISOString(),
});

describe('Sidebar', () => {
  const defaultProps = {
    conversations: [] as ConversationSummary[],
    selectedId: null,
    onSelectConversation: jest.fn(),
    onNewChat: jest.fn(),
    isOpen: true,
    onToggle: jest.fn(),
  };

  it('renders sidebar with title', () => {
    render(<Sidebar {...defaultProps} />);
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    expect(screen.getByText('Dining Philosophers')).toBeInTheDocument();
  });

  it('renders Dijkstra avatar before title', () => {
    const { container } = render(<Sidebar {...defaultProps} />);

    // Find the header link that contains both text and icon
    const headerLink = container.querySelector('a[href*="github.com"]');
    expect(headerLink).toBeInTheDocument();

    // Get all child nodes to verify order
    const children = Array.from(headerLink?.childNodes || []);

    // Text node should contain "Dining Philosophers"
    const textNode = children.find(
      (node) =>
        node.nodeType === Node.TEXT_NODE &&
        node.textContent?.includes('Dining Philosophers')
    );
    expect(textNode).toBeTruthy();

    // Image should come before the text
    const avatar = screen.getByAltText('Dijkstra');
    expect(avatar).toBeInTheDocument();
    expect(avatar).toHaveAttribute('src');

    // Verify the image is before the text node in DOM order
    const textIndex = children.indexOf(textNode!);
    const imageIndex = children.findIndex(
      (node) => node === avatar || node.contains(avatar)
    );
    expect(imageIndex).toBeLessThan(textIndex);
  });

  it('renders new chat button', () => {
    render(<Sidebar {...defaultProps} />);
    expect(screen.getByTestId('new-chat-button')).toBeInTheDocument();
    expect(screen.getByText('New Conversation')).toBeInTheDocument();
  });

  it('calls onNewChat when new chat button is clicked', () => {
    const onNewChat = jest.fn();
    render(<Sidebar {...defaultProps} onNewChat={onNewChat} />);

    fireEvent.click(screen.getByTestId('new-chat-button'));
    expect(onNewChat).toHaveBeenCalled();
  });

  it('renders conversation list', () => {
    const conversations = [
      createConversation('1', 'Philosophy'),
      createConversation('2', 'Science'),
    ];
    render(<Sidebar {...defaultProps} conversations={conversations} />);

    expect(screen.getByText('Philosophy')).toBeInTheDocument();
    expect(screen.getByText('Science')).toBeInTheDocument();
  });

  it('passes onSelect to conversation list', () => {
    const onSelectConversation = jest.fn();
    const conversations = [createConversation('1', 'Philosophy')];
    render(
      <Sidebar
        {...defaultProps}
        conversations={conversations}
        onSelectConversation={onSelectConversation}
      />
    );

    fireEvent.click(screen.getByText('Philosophy'));
    expect(onSelectConversation).toHaveBeenCalledWith('1');
  });

  it('toggles mobile overlay', () => {
    render(<Sidebar {...defaultProps} isOpen={true} />);
    expect(screen.getByTestId('sidebar-overlay')).toBeInTheDocument();
  });

  it('calls onToggle when overlay is clicked', () => {
    const onToggle = jest.fn();
    render(<Sidebar {...defaultProps} isOpen={true} onToggle={onToggle} />);

    fireEvent.click(screen.getByTestId('sidebar-overlay'));
    expect(onToggle).toHaveBeenCalled();
  });

  // Hamburger menu button moved to ChatArea header (see issue #204)
  // This test is no longer needed since Sidebar doesn't render the menu button

  it('displays username when provided', () => {
    render(<Sidebar {...defaultProps} username="testuser" />);
    expect(screen.getByText('testuser')).toBeInTheDocument();
    expect(screen.getByText('T')).toBeInTheDocument(); // Avatar initial
  });

  it('displays logout button when username is provided', () => {
    render(<Sidebar {...defaultProps} username="testuser" />);
    expect(screen.getByTestId('logout-button')).toBeInTheDocument();
  });

  it('calls onLogout when logout button is clicked', () => {
    const onLogout = jest.fn();
    render(
      <Sidebar {...defaultProps} username="testuser" onLogout={onLogout} />
    );

    fireEvent.click(screen.getByTestId('logout-button'));
    expect(onLogout).toHaveBeenCalled();
  });

  it('shows default footer text when no username', () => {
    render(<Sidebar {...defaultProps} />);
    expect(
      screen.getByText('Discuss ideas with AI-simulated thinkers')
    ).toBeInTheDocument();
  });

  it('renders bug report link when username is provided', () => {
    render(<Sidebar {...defaultProps} username="testuser" />);
    const bugReportLink = screen.getByTestId('bug-report-link');
    expect(bugReportLink).toBeInTheDocument();
    expect(bugReportLink).toHaveAttribute('target', '_blank');
    expect(bugReportLink).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('bug report URL includes username in the body', () => {
    render(<Sidebar {...defaultProps} username="testuser" />);
    const bugReportLink = screen.getByTestId(
      'bug-report-link'
    ) as HTMLAnchorElement;

    const url = bugReportLink.href;
    const decodedUrl = decodeURIComponent(url);

    // Check that URL contains GitHub issue creation path
    expect(url).toContain(
      'github.com/jeremymatthewwerner/thinkers-chat/issues/new'
    );

    // Check that user info is in the body
    expect(decodedUrl).toContain('testuser');
    expect(decodedUrl).toContain('Filed from thinkers-chat app');
  });

  it('bug report URL includes display name when provided', () => {
    render(
      <Sidebar {...defaultProps} username="testuser" displayName="Test User" />
    );
    const bugReportLink = screen.getByTestId(
      'bug-report-link'
    ) as HTMLAnchorElement;

    const decodedUrl = decodeURIComponent(bugReportLink.href);
    expect(decodedUrl).toContain('Display Name: Test User');
    expect(decodedUrl).toContain('Filed from thinkers-chat app by Test User');
  });

  it('bug report URL includes browser and OS information', () => {
    render(<Sidebar {...defaultProps} username="testuser" />);
    const bugReportLink = screen.getByTestId(
      'bug-report-link'
    ) as HTMLAnchorElement;

    const decodedUrl = decodeURIComponent(bugReportLink.href);
    expect(decodedUrl).toContain('Browser:');
    expect(decodedUrl).toContain('OS:');
    expect(decodedUrl).toContain('User Agent:');
  });
});
