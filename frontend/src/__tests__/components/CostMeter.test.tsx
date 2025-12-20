import { render, screen } from '@testing-library/react';
import { CostMeter } from '@/components/CostMeter';

describe('CostMeter', () => {
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
});
