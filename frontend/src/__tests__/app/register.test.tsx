/**
 * Tests for the Register page component.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RegisterPage from '@/app/register/page';
import { useAuth } from '@/contexts';
import { useRouter } from 'next/navigation';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock useAuth context
jest.mock('@/contexts', () => ({
  useAuth: jest.fn(),
}));

describe('RegisterPage', () => {
  const mockRegister = jest.fn();
  const mockRouter = {
    push: jest.fn(),
    replace: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
    (useAuth as jest.Mock).mockReturnValue({
      register: mockRegister,
      isAuthenticated: false,
      isLoading: false,
    });
  });

  it('renders register form with blue submit button', () => {
    render(<RegisterPage />);

    expect(screen.getByText('Create an Account')).toBeInTheDocument();
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
    expect(
      screen.getByLabelText(/What should we call you/i)
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument();

    const submitButton = screen.getByRole('button', {
      name: /create account/i,
    });
    expect(submitButton).toBeInTheDocument();

    // Check that button has blue background color classes
    expect(submitButton).toHaveClass('bg-blue-600');
    expect(submitButton).toHaveClass('hover:bg-blue-700');
  });

  it('shows error for mismatched passwords', async () => {
    const user = userEvent.setup();

    render(<RegisterPage />);

    await user.type(screen.getByLabelText('Username'), 'newuser');
    await user.type(
      screen.getByLabelText(/What should we call you/i),
      'New User'
    );
    await user.type(screen.getByLabelText('Password'), 'password123');
    await user.type(screen.getByLabelText('Confirm Password'), 'different');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
    });
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it('shows error for short password', async () => {
    const user = userEvent.setup();

    render(<RegisterPage />);

    await user.type(screen.getByLabelText('Username'), 'newuser');
    await user.type(
      screen.getByLabelText(/What should we call you/i),
      'New User'
    );
    await user.type(screen.getByLabelText('Password'), '12345');
    await user.type(screen.getByLabelText('Confirm Password'), '12345');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(
        screen.getByText('Password must be at least 6 characters')
      ).toBeInTheDocument();
    });
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it('submits form with valid data', async () => {
    const user = userEvent.setup();
    mockRegister.mockResolvedValue(undefined);

    render(<RegisterPage />);

    await user.type(screen.getByLabelText('Username'), 'newuser');
    await user.type(
      screen.getByLabelText(/What should we call you/i),
      'New User'
    );
    await user.type(screen.getByLabelText('Password'), 'password123');
    await user.type(screen.getByLabelText('Confirm Password'), 'password123');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith(
        'newuser',
        'New User',
        'password123'
      );
      expect(mockRouter.push).toHaveBeenCalledWith('/');
    });
  });
});
