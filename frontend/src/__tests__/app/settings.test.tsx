/**
 * Tests for the Settings page component.
 *
 * Covers:
 * - Rendering settings page for authenticated user
 * - Redirect to login when unauthenticated
 * - Loading state display
 * - Display name update (success, validation errors, API errors)
 * - Password change (success, validation errors, API errors)
 * - Feedback info save and clear
 * - Language selector
 * - Theme selector
 * - Back to chat navigation
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SettingsPage from '@/app/settings/page';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTheme } from '@/contexts';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api';
import * as FeedbackModal from '@/components/FeedbackModal';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock contexts
jest.mock('@/contexts/AuthContext', () => {
  const actual = jest.requireActual('@/contexts/AuthContext');
  return {
    ...actual,
    useAuth: jest.fn(),
  };
});

jest.mock('@/contexts/LanguageContext', () => {
  const actual = jest.requireActual('@/contexts/LanguageContext');
  return {
    ...actual,
    useLanguage: jest.fn(),
  };
});

jest.mock('@/contexts', () => {
  const actual = jest.requireActual('@/contexts');
  return {
    ...actual,
    useTheme: jest.fn(),
  };
});

// Mock api
jest.mock('@/lib/api', () => ({
  changePassword: jest.fn(),
  updateLanguage: jest.fn(),
}));

// Mock FeedbackModal helpers
jest.mock('@/components/FeedbackModal', () => ({
  getSavedFeedbackInfo: jest.fn(),
  saveFeedbackInfo: jest.fn(),
  clearFeedbackInfo: jest.fn(),
}));

// English translations (subset needed for tests)
const mockT = {
  common: { loading: 'Loading...' },
  settingsPage: {
    title: 'Settings',
    description: 'Manage your account settings',
    backToChat: 'Back to Chat',
    profileSection: 'Profile',
    displayName: 'Display Name',
    displayNamePlaceholder: 'Enter display name',
    displayNameHelp: 'This name is shown to other users',
    displayNameRequired: 'Display name is required',
    displayNameTooLong: 'Display name must be 100 characters or less',
    displayNameUpdated: 'Display name updated successfully',
    displayNameFailed: 'Failed to update display name',
    updating: 'Updating...',
    updateDisplayName: 'Update Display Name',
    languageSection: 'Language',
    preferredLanguage: 'Preferred Language',
    themeSection: 'Appearance',
    themePreference: 'Theme',
    themeSystem: 'System',
    themeLight: 'Light',
    themeDark: 'Dark',
    themeHelp: 'Choose how the app looks',
    feedbackInfoSection: 'Feedback Contact',
    feedbackInfoDescription: 'Save your contact info for feedback',
    savedFeedbackName: 'Name',
    savedFeedbackEmail: 'Email',
    updateFeedbackInfo: 'Save',
    clearFeedbackInfo: 'Clear',
    feedbackInfoUpdated: 'Feedback info saved',
    feedbackInfoCleared: 'Feedback info cleared',
    passwordSection: 'Change Password',
    currentPassword: 'Current Password',
    currentPasswordPlaceholder: 'Enter current password',
    currentPasswordRequired: 'Current password is required',
    newPassword: 'New Password',
    newPasswordPlaceholder: 'Enter new password',
    newPasswordRequired: 'New password is required',
    passwordTooShort: 'Password must be at least 6 characters',
    confirmPassword: 'Confirm Password',
    confirmPasswordPlaceholder: 'Confirm new password',
    passwordsDoNotMatch: 'Passwords do not match',
    changePassword: 'Change Password',
    changingPassword: 'Changing...',
    passwordChanged: 'Password changed successfully',
    passwordChangeFailed: 'Failed to change password',
  },
  languages: {
    en: 'English',
    es: 'Spanish',
    fr: 'French',
    de: 'German',
    hi: 'Hindi',
  },
  feedbackModal: {
    namePlaceholder: 'Your name',
    emailPlaceholder: 'your@email.com',
  },
};

const mockRouter = { push: jest.fn(), replace: jest.fn() };
const mockUpdateDisplayName = jest.fn();
const mockSetTheme = jest.fn();
const mockSetLocale = jest.fn();

function setupMocks(
  overrides: {
    user?: object | null;
    isLoading?: boolean;
    theme?: string;
    locale?: string;
  } = {}
) {
  const user =
    'user' in overrides
      ? overrides.user
      : {
          id: 'user-1',
          username: 'testuser',
          display_name: 'Test User',
          language_preference: 'en',
        };

  (useRouter as jest.Mock).mockReturnValue(mockRouter);
  (useAuth as jest.Mock).mockReturnValue({
    user,
    isLoading: overrides.isLoading ?? false,
    isAuthenticated: !!user,
    updateDisplayName: mockUpdateDisplayName,
  });
  (useLanguage as jest.Mock).mockReturnValue({
    t: mockT,
    locale: overrides.locale ?? 'en',
    setLocale: mockSetLocale,
  });
  (useTheme as jest.Mock).mockReturnValue({
    theme: overrides.theme ?? 'system',
    setTheme: mockSetTheme,
    resolvedTheme: 'light',
  });
  (FeedbackModal.getSavedFeedbackInfo as jest.Mock).mockReturnValue({
    name: '',
    email: '',
  });
}

describe('SettingsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupMocks();
  });

  describe('Authentication states', () => {
    it('renders loading state when auth is loading', () => {
      setupMocks({ isLoading: true, user: null });
      render(<SettingsPage />);
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('redirects to login when user is null and not loading', () => {
      setupMocks({ user: null, isLoading: false });
      render(<SettingsPage />);
      expect(mockRouter.push).toHaveBeenCalledWith('/login');
    });

    it('renders null (no content) when user is null and not loading', () => {
      setupMocks({ user: null, isLoading: false });
      const { container } = render(<SettingsPage />);
      // Should render null - no settings content
      expect(screen.queryByText('Settings')).not.toBeInTheDocument();
    });

    it('renders settings page when user is authenticated', () => {
      render(<SettingsPage />);
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });
  });

  describe('Page navigation', () => {
    it('navigates back to chat when back button is clicked', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.click(screen.getByText('Back to Chat'));
      expect(mockRouter.push).toHaveBeenCalledWith('/');
    });
  });

  describe('Display name section', () => {
    it('renders profile section with display name field', () => {
      render(<SettingsPage />);
      expect(screen.getByText('Profile')).toBeInTheDocument();
      expect(screen.getByLabelText('Display Name')).toBeInTheDocument();
    });

    it('initializes display name from user data', async () => {
      render(<SettingsPage />);
      await waitFor(() => {
        const input = screen.getByLabelText('Display Name');
        expect(input).toHaveValue('Test User');
      });
    });

    it('shows error when submitting empty display name', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      const input = screen.getByLabelText('Display Name');
      await user.clear(input);
      await user.click(
        screen.getByRole('button', { name: 'Update Display Name' })
      );

      expect(screen.getByText('Display name is required')).toBeInTheDocument();
    });

    it('shows error when display name exceeds 100 characters', async () => {
      const user = userEvent.setup();
      const { fireEvent } = await import('@testing-library/react');
      render(<SettingsPage />);

      // The input has maxLength=100 but the validation is done in handleUpdateDisplayName
      // We use fireEvent.change to bypass browser maxLength restriction
      const input = screen.getByLabelText('Display Name');
      fireEvent.change(input, { target: { value: 'a'.repeat(101) } });

      await user.click(
        screen.getByRole('button', { name: 'Update Display Name' })
      );

      expect(
        screen.getByText('Display name must be 100 characters or less')
      ).toBeInTheDocument();
    });

    it('calls updateDisplayName and shows success message', async () => {
      mockUpdateDisplayName.mockResolvedValueOnce(undefined);
      const user = userEvent.setup();
      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText('Display Name')).toHaveValue('Test User');
      });

      await user.click(
        screen.getByRole('button', { name: 'Update Display Name' })
      );

      await waitFor(() => {
        expect(mockUpdateDisplayName).toHaveBeenCalledWith('Test User');
        expect(
          screen.getByText('Display name updated successfully')
        ).toBeInTheDocument();
      });
    });

    it('shows error message when updateDisplayName fails with Error', async () => {
      mockUpdateDisplayName.mockRejectedValueOnce(
        new Error('Username already taken')
      );
      const user = userEvent.setup();
      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText('Display Name')).toHaveValue('Test User');
      });

      await user.click(
        screen.getByRole('button', { name: 'Update Display Name' })
      );

      await waitFor(() => {
        expect(screen.getByText('Username already taken')).toBeInTheDocument();
      });
    });

    it('shows fallback error message when updateDisplayName fails with non-Error', async () => {
      mockUpdateDisplayName.mockRejectedValueOnce('unknown error');
      const user = userEvent.setup();
      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText('Display Name')).toHaveValue('Test User');
      });

      await user.click(
        screen.getByRole('button', { name: 'Update Display Name' })
      );

      await waitFor(() => {
        expect(
          screen.getByText('Failed to update display name')
        ).toBeInTheDocument();
      });
    });

    it('disables button while updating', async () => {
      let resolveUpdate: () => void;
      mockUpdateDisplayName.mockReturnValueOnce(
        new Promise<void>((resolve) => {
          resolveUpdate = resolve;
        })
      );
      const user = userEvent.setup();
      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText('Display Name')).toHaveValue('Test User');
      });

      await user.click(
        screen.getByRole('button', { name: 'Update Display Name' })
      );

      // Button should be disabled and show loading text
      const button = screen.getByRole('button', { name: 'Updating...' });
      expect(button).toBeDisabled();

      resolveUpdate!();
    });
  });

  describe('Language section', () => {
    it('renders language section', () => {
      render(<SettingsPage />);
      expect(screen.getByText('Language')).toBeInTheDocument();
      expect(screen.getByLabelText('Preferred Language')).toBeInTheDocument();
    });

    it('calls setLocale when language is changed', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.selectOptions(
        screen.getByLabelText('Preferred Language'),
        'es'
      );
      expect(mockSetLocale).toHaveBeenCalledWith('es');
    });

    it('shows current locale as selected', () => {
      setupMocks({ locale: 'fr' });
      render(<SettingsPage />);
      const select = screen.getByLabelText(
        'Preferred Language'
      ) as HTMLSelectElement;
      expect(select.value).toBe('fr');
    });
  });

  describe('Theme section', () => {
    it('renders theme section', () => {
      render(<SettingsPage />);
      expect(screen.getByText('Appearance')).toBeInTheDocument();
      expect(screen.getByLabelText('Theme')).toBeInTheDocument();
    });

    it('calls setTheme when theme is changed', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.selectOptions(screen.getByLabelText('Theme'), 'dark');
      expect(mockSetTheme).toHaveBeenCalledWith('dark');
    });

    it('shows current theme as selected', () => {
      setupMocks({ theme: 'dark' });
      render(<SettingsPage />);
      const select = screen.getByLabelText('Theme') as HTMLSelectElement;
      expect(select.value).toBe('dark');
    });
  });

  describe('Feedback info section', () => {
    it('renders feedback contact section', () => {
      render(<SettingsPage />);
      expect(screen.getByText('Feedback Contact')).toBeInTheDocument();
    });

    it('loads saved feedback info on mount', () => {
      (FeedbackModal.getSavedFeedbackInfo as jest.Mock).mockReturnValue({
        name: 'John Doe',
        email: 'john@example.com',
      });
      render(<SettingsPage />);

      expect(screen.getByTestId('settings-feedback-name')).toHaveValue(
        'John Doe'
      );
      expect(screen.getByTestId('settings-feedback-email')).toHaveValue(
        'john@example.com'
      );
    });

    it('calls saveFeedbackInfo and shows success on form submit', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      const nameInput = screen.getByTestId('settings-feedback-name');
      const emailInput = screen.getByTestId('settings-feedback-email');

      await user.type(nameInput, 'Jane Smith');
      await user.type(emailInput, 'jane@example.com');
      await user.click(screen.getByTestId('update-feedback-info'));

      expect(FeedbackModal.saveFeedbackInfo).toHaveBeenCalledWith(
        'Jane Smith',
        'jane@example.com'
      );
      expect(screen.getByText('Feedback info saved')).toBeInTheDocument();
    });

    it('calls clearFeedbackInfo and clears fields', async () => {
      (FeedbackModal.getSavedFeedbackInfo as jest.Mock).mockReturnValue({
        name: 'John Doe',
        email: 'john@example.com',
      });
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.click(screen.getByTestId('clear-feedback-info'));

      expect(FeedbackModal.clearFeedbackInfo).toHaveBeenCalled();
      expect(screen.getByTestId('settings-feedback-name')).toHaveValue('');
      expect(screen.getByTestId('settings-feedback-email')).toHaveValue('');
      expect(screen.getByText('Feedback info cleared')).toBeInTheDocument();
    });
  });

  describe('Change password section', () => {
    it('renders password change section', () => {
      render(<SettingsPage />);
      // The section heading 'Change Password' appears as an h2
      const heading = screen.getByRole('heading', { name: 'Change Password' });
      expect(heading).toBeInTheDocument();
      expect(screen.getByLabelText('Current Password')).toBeInTheDocument();
      expect(screen.getByLabelText('New Password')).toBeInTheDocument();
      expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument();
    });

    it('shows error when current password is empty', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      expect(
        screen.getByText('Current password is required')
      ).toBeInTheDocument();
    });

    it('shows error when new password is empty', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.type(screen.getByLabelText('Current Password'), 'oldpass');
      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      expect(screen.getByText('New password is required')).toBeInTheDocument();
    });

    it('shows error when new password is too short', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.type(screen.getByLabelText('Current Password'), 'oldpass');
      await user.type(screen.getByLabelText('New Password'), 'abc');
      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      expect(
        screen.getByText('Password must be at least 6 characters')
      ).toBeInTheDocument();
    });

    it('shows error when passwords do not match', async () => {
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.type(screen.getByLabelText('Current Password'), 'oldpass');
      await user.type(screen.getByLabelText('New Password'), 'newpass123');
      await user.type(screen.getByLabelText('Confirm Password'), 'newpass456');
      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
    });

    it('calls changePassword and shows success message', async () => {
      (api.changePassword as jest.Mock).mockResolvedValueOnce(undefined);
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.type(screen.getByLabelText('Current Password'), 'oldpass123');
      await user.type(screen.getByLabelText('New Password'), 'newpass123');
      await user.type(screen.getByLabelText('Confirm Password'), 'newpass123');
      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      await waitFor(() => {
        expect(api.changePassword).toHaveBeenCalledWith(
          'oldpass123',
          'newpass123'
        );
        expect(
          screen.getByText('Password changed successfully')
        ).toBeInTheDocument();
      });
    });

    it('clears password fields on successful change', async () => {
      (api.changePassword as jest.Mock).mockResolvedValueOnce(undefined);
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.type(screen.getByLabelText('Current Password'), 'oldpass123');
      await user.type(screen.getByLabelText('New Password'), 'newpass123');
      await user.type(screen.getByLabelText('Confirm Password'), 'newpass123');
      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      await waitFor(() => {
        expect(screen.getByLabelText('Current Password')).toHaveValue('');
        expect(screen.getByLabelText('New Password')).toHaveValue('');
        expect(screen.getByLabelText('Confirm Password')).toHaveValue('');
      });
    });

    it('shows error message when changePassword fails with Error', async () => {
      (api.changePassword as jest.Mock).mockRejectedValueOnce(
        new Error('Invalid current password')
      );
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.type(screen.getByLabelText('Current Password'), 'wrongpass');
      await user.type(screen.getByLabelText('New Password'), 'newpass123');
      await user.type(screen.getByLabelText('Confirm Password'), 'newpass123');
      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      await waitFor(() => {
        expect(
          screen.getByText('Invalid current password')
        ).toBeInTheDocument();
      });
    });

    it('shows fallback error when changePassword fails with non-Error', async () => {
      (api.changePassword as jest.Mock).mockRejectedValueOnce('unknown');
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.type(screen.getByLabelText('Current Password'), 'oldpass');
      await user.type(screen.getByLabelText('New Password'), 'newpass123');
      await user.type(screen.getByLabelText('Confirm Password'), 'newpass123');
      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      await waitFor(() => {
        expect(
          screen.getByText('Failed to change password')
        ).toBeInTheDocument();
      });
    });

    it('disables button while changing password', async () => {
      let resolveChange: () => void;
      (api.changePassword as jest.Mock).mockReturnValueOnce(
        new Promise<void>((resolve) => {
          resolveChange = resolve;
        })
      );
      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.type(screen.getByLabelText('Current Password'), 'oldpass');
      await user.type(screen.getByLabelText('New Password'), 'newpass123');
      await user.type(screen.getByLabelText('Confirm Password'), 'newpass123');
      await user.click(screen.getByRole('button', { name: 'Change Password' }));

      const button = screen.getByRole('button', { name: 'Changing...' });
      expect(button).toBeDisabled();

      resolveChange!();
    });
  });
});
