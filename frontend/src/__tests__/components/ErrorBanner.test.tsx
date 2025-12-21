import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ErrorBanner } from '@/components/ErrorBanner';

describe('ErrorBanner', () => {
  it('should render error message', () => {
    render(<ErrorBanner message="Test error message" />);
    expect(screen.getByTestId('error-banner')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Test error message')).toBeInTheDocument();
  });

  it('should not render when message is empty', () => {
    render(<ErrorBanner message="" />);
    expect(screen.queryByTestId('error-banner')).not.toBeInTheDocument();
  });

  it('should render dismiss button when onDismiss is provided', () => {
    const onDismiss = jest.fn();
    render(<ErrorBanner message="Test error" onDismiss={onDismiss} />);
    expect(screen.getByTestId('dismiss-error-button')).toBeInTheDocument();
  });

  it('should not render dismiss button when onDismiss is not provided', () => {
    render(<ErrorBanner message="Test error" />);
    expect(
      screen.queryByTestId('dismiss-error-button')
    ).not.toBeInTheDocument();
  });

  it('should call onDismiss when dismiss button is clicked', async () => {
    const user = userEvent.setup();
    const onDismiss = jest.fn();
    render(<ErrorBanner message="Test error" onDismiss={onDismiss} />);

    const dismissButton = screen.getByTestId('dismiss-error-button');
    await user.click(dismissButton);

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('should render with red styling', () => {
    render(<ErrorBanner message="Test error" />);
    const banner = screen.getByTestId('error-banner');
    expect(banner).toHaveClass('bg-red-50');
    expect(banner).toHaveClass('border-red-200');
  });

  it('should render billing error message', () => {
    const billingError =
      'Spend limit reached ($10.00/$10.00). Contact admin to increase your limit.';
    render(<ErrorBanner message={billingError} />);
    expect(screen.getByText(billingError)).toBeInTheDocument();
  });
});
