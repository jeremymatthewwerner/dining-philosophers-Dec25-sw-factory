/**
 * Tests for SpendLimitBanner component.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { SpendLimitBanner } from '@/components/SpendLimitBanner';

describe('SpendLimitBanner', () => {
  it('renders nothing when spend is below 85%', () => {
    const { container } = render(
      <SpendLimitBanner currentSpend={5} spendLimit={10} isExceeded={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders warning banner when spend is at 85%', () => {
    render(
      <SpendLimitBanner currentSpend={8.5} spendLimit={10} isExceeded={false} />
    );
    expect(screen.getByTestId('spend-limit-banner')).toBeInTheDocument();
    expect(screen.getByText('Approaching spend limit')).toBeInTheDocument();
    expect(screen.getByText('$8.50 / $10.00 (85%)')).toBeInTheDocument();
  });

  it('renders warning banner when spend is at 95%', () => {
    render(
      <SpendLimitBanner currentSpend={9.5} spendLimit={10} isExceeded={false} />
    );
    expect(screen.getByTestId('spend-limit-banner')).toBeInTheDocument();
    expect(screen.getByText('Approaching spend limit')).toBeInTheDocument();
    expect(screen.getByText('$9.50 / $10.00 (95%)')).toBeInTheDocument();
  });

  it('renders exceeded banner when limit is exceeded', () => {
    render(
      <SpendLimitBanner currentSpend={10.5} spendLimit={10} isExceeded={true} />
    );
    expect(screen.getByTestId('spend-limit-banner')).toBeInTheDocument();
    expect(screen.getByText('Spend limit reached')).toBeInTheDocument();
    expect(
      screen.getByText(
        /\$10\.50 \/ \$10\.00 \(100%\) - Contact admin to increase your limit/
      )
    ).toBeInTheDocument();
  });

  it('shows dismiss button for warning but not exceeded state', () => {
    const onDismiss = jest.fn();
    const { rerender } = render(
      <SpendLimitBanner
        currentSpend={9}
        spendLimit={10}
        isExceeded={false}
        onDismiss={onDismiss}
      />
    );

    // Warning state should have dismiss button
    const dismissButton = screen.getByLabelText('Dismiss');
    expect(dismissButton).toBeInTheDocument();
    fireEvent.click(dismissButton);
    expect(onDismiss).toHaveBeenCalled();

    // Exceeded state should not have dismiss button
    rerender(
      <SpendLimitBanner
        currentSpend={10.5}
        spendLimit={10}
        isExceeded={true}
        onDismiss={onDismiss}
      />
    );
    expect(screen.queryByLabelText('Dismiss')).not.toBeInTheDocument();
  });

  it('does not show dismiss button when onDismiss is not provided', () => {
    render(
      <SpendLimitBanner currentSpend={9} spendLimit={10} isExceeded={false} />
    );
    expect(screen.queryByLabelText('Dismiss')).not.toBeInTheDocument();
  });

  it('caps percentage display at 100%', () => {
    render(
      <SpendLimitBanner currentSpend={15} spendLimit={10} isExceeded={true} />
    );
    expect(screen.getByText(/\(100%\)/)).toBeInTheDocument();
  });
});
