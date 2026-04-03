/**
 * Tests for the Admin page component, focusing on sorting functionality.
 */

import React from 'react';
import {
  render as rtlRender,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminPage from '@/app/admin/page';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock the auth context module to control useAuth return values
const mockUseAuth = jest.fn();
jest.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock API functions
jest.mock('@/lib/api', () => ({
  getAdminUsers: jest.fn(),
  deleteUser: jest.fn(),
  updateUserSpendLimit: jest.fn(),
}));

const mockUsers = [
  {
    id: 'user-1',
    username: 'alice',
    display_name: 'Alice',
    is_admin: false,
    total_spend: 50.0,
    spend_limit: 100.0,
    language_preference: 'en',
    created_at: '2024-01-15T10:00:00Z',
    conversation_count: 5,
  },
  {
    id: 'user-2',
    username: 'bob',
    display_name: 'Bob',
    is_admin: true,
    total_spend: 25.0,
    spend_limit: 200.0,
    language_preference: 'en',
    created_at: '2024-02-20T10:00:00Z',
    conversation_count: 10,
  },
  {
    id: 'user-3',
    username: 'charlie',
    display_name: 'Charlie',
    is_admin: false,
    total_spend: 75.0,
    spend_limit: 50.0,
    language_preference: 'en',
    created_at: '2024-01-01T10:00:00Z',
    conversation_count: 3,
  },
];

// Admin page manages its own auth via mocked context, so plain rtlRender (no
// provider wrappers) is correct here. The wrapper is intentionally minimal.
function render(ui: React.ReactElement) {
  return rtlRender(ui);
}

/**
 * Renders the AdminPage and waits for the admin panel header to appear.
 *
 * Eliminates the 10-occurrence pattern of:
 *   render(<AdminPage />);
 *   await waitFor(() => {
 *     expect(screen.getByText('Admin Panel')).toBeInTheDocument();
 *   });
 *
 * Tests that only need the page loaded (not specific interactions) use this
 * helper so setup intent is clear and the repeated assertion is not noisy.
 */
async function renderAdminPage() {
  render(<AdminPage />);
  await waitFor(() => {
    expect(screen.getByText('Admin Panel')).toBeInTheDocument();
  });
}

describe('AdminPage', () => {
  const mockRouter = {
    push: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
    mockUseAuth.mockReturnValue({
      user: { id: 'admin-1', is_admin: true },
      isLoading: false,
    });
    (api.getAdminUsers as jest.Mock).mockResolvedValue(mockUsers);
  });

  it('renders the admin page with users table', async () => {
    await renderAdminPage();

    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
    expect(screen.getByText('charlie')).toBeInTheDocument();
  });

  describe('Column Sorting', () => {
    it('displays sort indicators on column headers', async () => {
      await renderAdminPage();

      // Username column should have active sort indicator (default sorted column)
      const usernameHeader = screen.getByRole('columnheader', {
        name: /username/i,
      });
      expect(usernameHeader).toHaveTextContent('▲');

      // Other columns should have inactive sort indicator
      const roleHeader = screen.getByRole('columnheader', { name: /role/i });
      expect(roleHeader).toHaveTextContent('⇅');
    });

    it('sorts by username in ascending order by default', async () => {
      await renderAdminPage();

      const rows = screen.getAllByRole('row').slice(1); // Skip header row
      const usernames = rows.map((row) => {
        const cells = within(row).getAllByRole('cell');
        return cells[0]?.textContent;
      });

      // Should be in alphabetical order
      expect(usernames[0]).toContain('alice');
      expect(usernames[1]).toContain('bob');
      expect(usernames[2]).toContain('charlie');
    });

    it('toggles sort direction when clicking the same column', async () => {
      const user = userEvent.setup();
      await renderAdminPage();

      const usernameHeader = screen.getByRole('columnheader', {
        name: /username/i,
      });

      // Click to toggle to descending
      await user.click(usernameHeader);

      // Check sort indicator changed
      expect(usernameHeader).toHaveTextContent('▼');

      // Check order reversed
      const rows = screen.getAllByRole('row').slice(1);
      const usernames = rows.map((row) => {
        const cells = within(row).getAllByRole('cell');
        return cells[0]?.textContent;
      });

      expect(usernames[0]).toContain('charlie');
      expect(usernames[1]).toContain('bob');
      expect(usernames[2]).toContain('alice');
    });

    it('sorts by conversations column (numeric)', async () => {
      const user = userEvent.setup();
      await renderAdminPage();

      const conversationsHeader = screen.getByRole('columnheader', {
        name: /conversations/i,
      });

      await user.click(conversationsHeader);

      // Check ascending order (3, 5, 10)
      const rows = screen.getAllByRole('row').slice(1);
      const counts = rows.map((row) => {
        const cells = within(row).getAllByRole('cell');
        return cells[2]?.textContent;
      });

      expect(counts[0]).toBe('3');
      expect(counts[1]).toBe('5');
      expect(counts[2]).toBe('10');
    });

    it('sorts by total spend column (numeric)', async () => {
      const user = userEvent.setup();
      await renderAdminPage();

      const spendHeader = screen.getByRole('columnheader', {
        name: /total spend/i,
      });

      await user.click(spendHeader);

      // Check ascending order ($25, $50, $75)
      const rows = screen.getAllByRole('row').slice(1);
      const spends = rows.map((row) => {
        const cells = within(row).getAllByRole('cell');
        return cells[3]?.textContent;
      });

      expect(spends[0]).toBe('$25.00');
      expect(spends[1]).toBe('$50.00');
      expect(spends[2]).toBe('$75.00');
    });

    it('sorts by spend limit column (numeric)', async () => {
      const user = userEvent.setup();
      await renderAdminPage();

      const spendLimitHeader = screen.getByRole('columnheader', {
        name: /spend limit/i,
      });

      await user.click(spendLimitHeader);

      // Check ascending order ($50, $100, $200)
      const rows = screen.getAllByRole('row').slice(1);
      const limits = rows.map((row) => {
        const cells = within(row).getAllByRole('cell');
        // Spend limit cell includes Edit button, just check it contains the value
        return cells[4]?.textContent;
      });

      expect(limits[0]).toContain('$50.00');
      expect(limits[1]).toContain('$100.00');
      expect(limits[2]).toContain('$200.00');
    });

    it('sorts by role column (admin first when ascending)', async () => {
      const user = userEvent.setup();
      await renderAdminPage();

      const roleHeader = screen.getByRole('columnheader', { name: /role/i });

      await user.click(roleHeader);

      // Admin should come first in ascending
      const rows = screen.getAllByRole('row').slice(1);
      const roles = rows.map((row) => {
        const cells = within(row).getAllByRole('cell');
        return cells[1]?.textContent;
      });

      expect(roles[0]).toBe('Admin');
      expect(roles[1]).toBe('User');
      expect(roles[2]).toBe('User');
    });

    it('sorts by joined date column', async () => {
      const user = userEvent.setup();
      await renderAdminPage();

      const joinedHeader = screen.getByRole('columnheader', {
        name: /joined/i,
      });

      await user.click(joinedHeader);

      // Check ascending order by date
      const rows = screen.getAllByRole('row').slice(1);
      const dates = rows.map((row) => {
        const cells = within(row).getAllByRole('cell');
        return cells[5]?.textContent;
      });

      // Jan 1, 2024 < Jan 15, 2024 < Feb 20, 2024
      expect(dates[0]).toBe('Jan 1, 2024');
      expect(dates[1]).toBe('Jan 15, 2024');
      expect(dates[2]).toBe('Feb 20, 2024');
    });

    it('resets to ascending when switching to a new column', async () => {
      const user = userEvent.setup();
      await renderAdminPage();

      const usernameHeader = screen.getByRole('columnheader', {
        name: /username/i,
      });
      const conversationsHeader = screen.getByRole('columnheader', {
        name: /conversations/i,
      });

      // Toggle username to descending
      await user.click(usernameHeader);
      expect(usernameHeader).toHaveTextContent('▼');

      // Switch to conversations - should reset to ascending
      await user.click(conversationsHeader);
      expect(conversationsHeader).toHaveTextContent('▲');
      expect(usernameHeader).toHaveTextContent('⇅');
    });

    it('actions column is not sortable', async () => {
      await renderAdminPage();

      const actionsHeader = screen.getByRole('columnheader', {
        name: /actions/i,
      });

      // Actions header should not have a sort indicator
      expect(actionsHeader).not.toHaveTextContent('⇅');
      expect(actionsHeader).not.toHaveTextContent('▲');
      expect(actionsHeader).not.toHaveTextContent('▼');

      // Actions header should not have cursor-pointer class
      expect(actionsHeader).not.toHaveClass('cursor-pointer');
    });
  });

  describe('Access Control', () => {
    it('redirects non-admin users to home', async () => {
      mockUseAuth.mockReturnValue({
        user: { id: 'user-1', is_admin: false },
        isLoading: false,
      });

      render(<AdminPage />);

      await waitFor(() => {
        expect(mockRouter.push).toHaveBeenCalledWith('/');
      });
    });

    it('redirects unauthenticated users to login', async () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isLoading: false,
      });

      render(<AdminPage />);

      await waitFor(() => {
        expect(mockRouter.push).toHaveBeenCalledWith('/login');
      });
    });
  });
});
