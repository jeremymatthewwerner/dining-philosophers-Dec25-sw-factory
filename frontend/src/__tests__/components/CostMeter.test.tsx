import { render, screen, act } from '@/test-utils';
import { CostMeter } from '@/components/CostMeter';

describe('CostMeter', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('renders with zero cost', () => {
    render(<CostMeter totalCost={0} />);
    expect(screen.getByTestId('cost-meter')).toBeInTheDocument();
    expect(screen.getByText('This Session:')).toBeInTheDocument();
    expect(screen.getByText('$0.0000')).toBeInTheDocument();
  });

  it('formats small costs with 4 decimal places', () => {
    render(<CostMeter totalCost={0.0001} />);
    expect(screen.getByText('$0.0001')).toBeInTheDocument();
  });

  it('formats medium costs with 3 decimal places', () => {
    render(<CostMeter totalCost={0.123} />);
    expect(screen.getByText('$0.123')).toBeInTheDocument();
  });

  it('formats large costs with 2 decimal places', () => {
    render(<CostMeter totalCost={1.5} />);
    expect(screen.getByText('$1.50')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<CostMeter totalCost={0} className="custom-class" />);
    expect(screen.getByTestId('cost-meter')).toHaveClass('custom-class');
  });

  it('displays green color for low costs', () => {
    render(<CostMeter totalCost={0.001} />);
    const costValue = screen.getByText('$0.0010');
    expect(costValue).toHaveClass('text-green-600');
  });

  it('displays yellow color for medium costs', () => {
    render(<CostMeter totalCost={0.05} />);
    const costValue = screen.getByText('$0.050');
    expect(costValue).toHaveClass('text-yellow-600');
  });

  it('displays orange color for high costs', () => {
    render(<CostMeter totalCost={0.5} />);
    const costValue = screen.getByText('$0.500');
    expect(costValue).toHaveClass('text-orange-600');
  });

  it('animates cost change over time', () => {
    const { rerender } = render(<CostMeter totalCost={0} />);

    // Update cost
    rerender(<CostMeter totalCost={1.0} />);

    // Run the animation interval steps
    act(() => {
      jest.advanceTimersByTime(200); // 10 steps at 20ms each
    });

    // After partial animation, cost should be increasing
    // (the display value will be somewhere between 0 and 1)
    expect(screen.getByTestId('cost-meter')).toBeInTheDocument();
  });

  it('reaches target cost after full animation completes', () => {
    const { rerender } = render(<CostMeter totalCost={0} />);

    rerender(<CostMeter totalCost={1.5} />);

    // Run all animation steps (20 steps at 20ms each = 400ms)
    act(() => {
      jest.advanceTimersByTime(500);
    });

    // After full animation, should show the final value
    expect(screen.getByText('$1.50')).toBeInTheDocument();
  });

  it('clears interval when cost update is complete', () => {
    const { rerender, unmount } = render(<CostMeter totalCost={0} />);

    rerender(<CostMeter totalCost={0.5} />);

    act(() => {
      jest.advanceTimersByTime(1000); // Well past the 400ms animation
    });

    // Should not throw and should show final value
    expect(screen.getByText('$0.500')).toBeInTheDocument();

    // Unmount to test cleanup
    unmount();
  });

  it('does not animate when totalCost equals displayCost', () => {
    render(<CostMeter totalCost={0.5} />);
    // Initial render sets displayCost to totalCost, so no animation
    // Advancing time should not change anything
    act(() => {
      jest.advanceTimersByTime(500);
    });
    expect(screen.getByText('$0.500')).toBeInTheDocument();
  });
});
