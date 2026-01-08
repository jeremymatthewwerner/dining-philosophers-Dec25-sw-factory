/**
 * Tests for UserMenu component - dropdown menu triggered by user badge
 */

import { fireEvent, render, screen, waitFor } from '@/test-utils';
import { UserMenu } from '../UserMenu';
import userEvent from '@testing-library/user-event';

describe('UserMenu', () => {
  const defaultProps = {
    username: 'testuser',
    displayName: 'Test User',
    isAdmin: false,
    bugReportUrl:
      'https://github.com/jeremymatthewwerner/dining-philosophers-Dec25-sw-factory/issues/new',
    onLogout: jest.fn(),
    onFeedbackClick: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Trigger Button', () => {
    it('renders user badge with display name and avatar initial', () => {
      render(<UserMenu {...defaultProps} />);

      expect(screen.getByTestId('user-menu-button')).toBeInTheDocument();
      expect(screen.getByText('Test User')).toBeInTheDocument();
      expect(screen.getByText('T')).toBeInTheDocument(); // Avatar initial
    });

    it('uses username when displayName is not provided', () => {
      render(<UserMenu {...defaultProps} displayName={null} />);

      expect(screen.getByText('testuser')).toBeInTheDocument();
      expect(screen.getByText('T')).toBeInTheDocument();
    });

    it('has correct aria attributes', () => {
      render(<UserMenu {...defaultProps} />);

      const button = screen.getByTestId('user-menu-button');
      expect(button).toHaveAttribute('aria-expanded', 'false');
      expect(button).toHaveAttribute('aria-haspopup', 'menu');
    });
  });

  describe('Dropdown Menu', () => {
    it('opens when button is clicked', () => {
      render(<UserMenu {...defaultProps} />);

      expect(
        screen.queryByTestId('user-menu-dropdown')
      ).not.toBeInTheDocument();

      fireEvent.click(screen.getByTestId('user-menu-button'));

      expect(screen.getByTestId('user-menu-dropdown')).toBeInTheDocument();
    });

    it('closes when button is clicked again', () => {
      render(<UserMenu {...defaultProps} />);

      fireEvent.click(screen.getByTestId('user-menu-button'));
      expect(screen.getByTestId('user-menu-dropdown')).toBeInTheDocument();

      fireEvent.click(screen.getByTestId('user-menu-button'));
      expect(
        screen.queryByTestId('user-menu-dropdown')
      ).not.toBeInTheDocument();
    });

    it('updates aria-expanded when menu opens/closes', () => {
      render(<UserMenu {...defaultProps} />);

      const button = screen.getByTestId('user-menu-button');
      expect(button).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'true');

      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });

    it('displays user info header in dropdown', () => {
      render(<UserMenu {...defaultProps} />);

      fireEvent.click(screen.getByTestId('user-menu-button'));

      // Display name appears twice - in button and in dropdown header
      const displayNames = screen.getAllByText('Test User');
      expect(displayNames.length).toBeGreaterThanOrEqual(2);

      // Username appears with @ prefix in header
      expect(screen.getByText('@testuser')).toBeInTheDocument();
    });

    it('does not show username in header when same as display name', () => {
      render(
        <UserMenu
          {...defaultProps}
          displayName="testuser"
          username="testuser"
        />
      );

      fireEvent.click(screen.getByTestId('user-menu-button'));

      // Should not show @testuser since display name equals username
      expect(screen.queryByText('@testuser')).not.toBeInTheDocument();
    });
  });

  describe('Menu Items', () => {
    it('shows feedback option', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      expect(screen.getByTestId('user-menu-feedback')).toBeInTheDocument();
    });

    it('shows bug report option with GitHub link', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      const bugReport = screen.getByTestId('user-menu-bug-report');
      expect(bugReport).toBeInTheDocument();
      expect(bugReport).toHaveAttribute('href', defaultProps.bugReportUrl);
      expect(bugReport).toHaveAttribute('target', '_blank');
      expect(bugReport).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('shows settings option', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      const settings = screen.getByTestId('user-menu-settings');
      expect(settings).toBeInTheDocument();
      expect(settings).toHaveAttribute('href', '/settings');
    });

    it('shows admin option when user is admin', () => {
      render(<UserMenu {...defaultProps} isAdmin={true} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      const admin = screen.getByTestId('user-menu-admin');
      expect(admin).toBeInTheDocument();
      expect(admin).toHaveAttribute('href', '/admin');
    });

    it('does not show admin option when user is not admin', () => {
      render(<UserMenu {...defaultProps} isAdmin={false} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      expect(screen.queryByTestId('user-menu-admin')).not.toBeInTheDocument();
    });

    it('shows sign out option', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      expect(screen.getByTestId('user-menu-signout')).toBeInTheDocument();
    });
  });

  describe('Menu Actions', () => {
    it('calls onFeedbackClick and closes menu when feedback is clicked', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));
      fireEvent.click(screen.getByTestId('user-menu-feedback'));

      expect(defaultProps.onFeedbackClick).toHaveBeenCalled();
      expect(
        screen.queryByTestId('user-menu-dropdown')
      ).not.toBeInTheDocument();
    });

    it('calls onLogout and closes menu when sign out is clicked', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));
      fireEvent.click(screen.getByTestId('user-menu-signout'));

      expect(defaultProps.onLogout).toHaveBeenCalled();
      expect(
        screen.queryByTestId('user-menu-dropdown')
      ).not.toBeInTheDocument();
    });

    it('closes menu when settings link is clicked', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));
      fireEvent.click(screen.getByTestId('user-menu-settings'));

      expect(
        screen.queryByTestId('user-menu-dropdown')
      ).not.toBeInTheDocument();
    });
  });

  describe('Close on Click Outside', () => {
    it('closes menu when clicking outside', async () => {
      render(
        <div>
          <div data-testid="outside">Outside</div>
          <UserMenu {...defaultProps} />
        </div>
      );

      fireEvent.click(screen.getByTestId('user-menu-button'));
      expect(screen.getByTestId('user-menu-dropdown')).toBeInTheDocument();

      fireEvent.mouseDown(screen.getByTestId('outside'));

      await waitFor(() => {
        expect(
          screen.queryByTestId('user-menu-dropdown')
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('Keyboard Navigation', () => {
    it('opens menu with Enter key', async () => {
      const user = userEvent.setup();
      render(<UserMenu {...defaultProps} />);

      const button = screen.getByTestId('user-menu-button');
      button.focus();

      await user.keyboard('{Enter}');

      expect(screen.getByTestId('user-menu-dropdown')).toBeInTheDocument();
    });

    it('opens menu with Space key', async () => {
      const user = userEvent.setup();
      render(<UserMenu {...defaultProps} />);

      const button = screen.getByTestId('user-menu-button');
      button.focus();

      await user.keyboard(' ');

      expect(screen.getByTestId('user-menu-dropdown')).toBeInTheDocument();
    });

    it('closes menu with Escape key', async () => {
      const user = userEvent.setup();
      render(<UserMenu {...defaultProps} />);

      fireEvent.click(screen.getByTestId('user-menu-button'));
      expect(screen.getByTestId('user-menu-dropdown')).toBeInTheDocument();

      await user.keyboard('{Escape}');

      expect(
        screen.queryByTestId('user-menu-dropdown')
      ).not.toBeInTheDocument();
    });

    it('navigates items with arrow keys', async () => {
      const user = userEvent.setup();
      render(<UserMenu {...defaultProps} />);

      fireEvent.click(screen.getByTestId('user-menu-button'));

      // First item should be focused when menu opens
      await waitFor(() => {
        expect(screen.getByTestId('user-menu-feedback')).toHaveFocus();
      });

      // Navigate down
      await user.keyboard('{ArrowDown}');
      expect(screen.getByTestId('user-menu-bug-report')).toHaveFocus();

      // Navigate down again
      await user.keyboard('{ArrowDown}');
      expect(screen.getByTestId('user-menu-settings')).toHaveFocus();

      // Navigate up
      await user.keyboard('{ArrowUp}');
      expect(screen.getByTestId('user-menu-bug-report')).toHaveFocus();
    });

    it('wraps around when navigating past last item', async () => {
      const user = userEvent.setup();
      render(<UserMenu {...defaultProps} />);

      fireEvent.click(screen.getByTestId('user-menu-button'));

      // Navigate to end
      await user.keyboard('{End}');
      expect(screen.getByTestId('user-menu-signout')).toHaveFocus();

      // Navigate down should wrap to first
      await user.keyboard('{ArrowDown}');
      expect(screen.getByTestId('user-menu-feedback')).toHaveFocus();
    });

    it('navigates to first item with Home key', async () => {
      const user = userEvent.setup();
      render(<UserMenu {...defaultProps} />);

      fireEvent.click(screen.getByTestId('user-menu-button'));

      // Navigate down a few times
      await user.keyboard('{ArrowDown}');
      await user.keyboard('{ArrowDown}');

      // Press Home
      await user.keyboard('{Home}');
      expect(screen.getByTestId('user-menu-feedback')).toHaveFocus();
    });

    it('navigates to last item with End key', async () => {
      const user = userEvent.setup();
      render(<UserMenu {...defaultProps} />);

      fireEvent.click(screen.getByTestId('user-menu-button'));

      await user.keyboard('{End}');
      expect(screen.getByTestId('user-menu-signout')).toHaveFocus();
    });

    it('activates item with Enter key', async () => {
      const user = userEvent.setup();
      render(<UserMenu {...defaultProps} />);

      fireEvent.click(screen.getByTestId('user-menu-button'));

      // Focus should be on feedback
      await waitFor(() => {
        expect(screen.getByTestId('user-menu-feedback')).toHaveFocus();
      });

      // Navigate to sign out
      await user.keyboard('{End}');

      // Activate with Enter
      await user.keyboard('{Enter}');

      expect(defaultProps.onLogout).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has role="menu" on dropdown', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      expect(screen.getByRole('menu')).toBeInTheDocument();
    });

    it('has role="menuitem" on each item', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      const menuItems = screen.getAllByRole('menuitem');
      expect(menuItems.length).toBeGreaterThan(0);
    });

    it('has aria-orientation on menu', () => {
      render(<UserMenu {...defaultProps} />);
      fireEvent.click(screen.getByTestId('user-menu-button'));

      expect(screen.getByRole('menu')).toHaveAttribute(
        'aria-orientation',
        'vertical'
      );
    });
  });
});
