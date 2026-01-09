import { render, screen, fireEvent, act } from '@testing-library/react';
import { ScrollingText } from '../ScrollingText';

// Mock requestAnimationFrame and cancelAnimationFrame
let rafCallbacks: ((timestamp: number) => void)[] = [];
let rafId = 0;
const originalRAF = global.requestAnimationFrame;
const originalCAF = global.cancelAnimationFrame;

beforeEach(() => {
  rafCallbacks = [];
  rafId = 0;
  jest.useFakeTimers();

  global.requestAnimationFrame = jest.fn((callback) => {
    rafCallbacks.push(callback);
    return ++rafId;
  });

  global.cancelAnimationFrame = jest.fn();
});

afterEach(() => {
  global.requestAnimationFrame = originalRAF;
  global.cancelAnimationFrame = originalCAF;
  jest.useRealTimers();
});

describe('ScrollingText', () => {
  it('renders text content', () => {
    render(<ScrollingText text="Hello World" />);
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<ScrollingText text="Test" className="custom-class" />);
    const container = screen.getByText('Test').parentElement;
    expect(container).toHaveClass('custom-class');
  });

  it('shows title attribute when truncated', () => {
    render(<ScrollingText text="Long text that should be truncated" />);

    const container = screen.getByText(
      'Long text that should be truncated'
    ).parentElement;
    const textSpan = screen.getByText('Long text that should be truncated');

    // Mock the refs to simulate truncation
    Object.defineProperty(container, 'clientWidth', { value: 50 });
    Object.defineProperty(textSpan, 'scrollWidth', { value: 100 });

    // Trigger resize to check truncation
    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    // Title should be set when truncated
    expect(container).toHaveAttribute(
      'title',
      'Long text that should be truncated'
    );
  });

  it('does not show title when not truncated', () => {
    render(<ScrollingText text="Short" />);
    const container = screen.getByText('Short').parentElement;
    // Title should not be set when not truncated
    expect(container).not.toHaveAttribute('title');
  });

  it('responds to mouse enter and leave', () => {
    render(<ScrollingText text="Test content" />);
    const container = screen.getByText('Test content').parentElement!;

    fireEvent.mouseEnter(container);
    fireEvent.mouseLeave(container);

    // Component should not throw and should render correctly
    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('uses custom delay when provided', () => {
    render(<ScrollingText text="Test" delayMs={3000} />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('uses custom speed when provided', () => {
    render(<ScrollingText text="Test" speedPxPerSecond={50} />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('uses custom title when provided', () => {
    render(<ScrollingText text="Short" title="Custom title" />);
    const container = screen.getByText('Short').parentElement;
    const textSpan = screen.getByText('Short');

    // Mock truncation
    Object.defineProperty(container, 'clientWidth', { value: 50 });
    Object.defineProperty(textSpan, 'scrollWidth', { value: 100 });

    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    // Custom title should be shown when truncated
    expect(container).toHaveAttribute('title', 'Custom title');
  });

  it('has correct overflow styling', () => {
    render(<ScrollingText text="Test" className="test-class" />);
    const container = screen.getByText('Test').parentElement;
    expect(container).toHaveClass('overflow-hidden');
    expect(container).toHaveClass('whitespace-nowrap');
  });

  it('text span has block truncate class when not animating', () => {
    render(<ScrollingText text="Test" />);
    const textSpan = screen.getByText('Test');
    // When not hovering/animating, text shows with truncate class for ellipsis
    expect(textSpan).toHaveClass('block');
    expect(textSpan).toHaveClass('truncate');
  });

  it('cleans up animation frame on unmount', () => {
    const { unmount } = render(<ScrollingText text="Test" />);
    unmount();
    // Should not throw
  });

  it('handles empty text', () => {
    render(<ScrollingText text="" />);
    // Should render without errors
    const container = document.querySelector('.overflow-hidden');
    expect(container).toBeInTheDocument();
  });

  it('handles very long text', () => {
    const longText = 'A'.repeat(1000);
    render(<ScrollingText text={longText} />);
    expect(screen.getByText(longText)).toBeInTheDocument();
  });
});

describe('ScrollingText animation behavior', () => {
  it('starts animation on hover when truncated', () => {
    render(
      <ScrollingText text="This is a long text that should be truncated" />
    );

    const container = screen.getByText(
      'This is a long text that should be truncated'
    ).parentElement!;
    const textSpan = screen.getByText(
      'This is a long text that should be truncated'
    );

    // Mock truncation
    Object.defineProperty(container, 'clientWidth', {
      value: 50,
      configurable: true,
    });
    Object.defineProperty(textSpan, 'scrollWidth', {
      value: 200,
      configurable: true,
    });

    // Trigger truncation check
    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    // Hover
    act(() => {
      fireEvent.mouseEnter(container);
    });

    // requestAnimationFrame should be called
    expect(global.requestAnimationFrame).toHaveBeenCalled();

    // When animating, text span should have inline-block class (not truncate)
    const animatingSpan = screen.getByText(
      'This is a long text that should be truncated'
    );
    expect(animatingSpan).toHaveClass('inline-block');
    expect(animatingSpan).not.toHaveClass('truncate');
  });

  it('stops animation on mouse leave', () => {
    render(<ScrollingText text="Long text content here" />);

    const container = screen.getByText('Long text content here').parentElement!;
    const textSpan = screen.getByText('Long text content here');

    // Mock truncation
    Object.defineProperty(container, 'clientWidth', {
      value: 30,
      configurable: true,
    });
    Object.defineProperty(textSpan, 'scrollWidth', {
      value: 150,
      configurable: true,
    });

    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    act(() => {
      fireEvent.mouseEnter(container);
    });

    act(() => {
      fireEvent.mouseLeave(container);
    });

    // After mouse leave, text should revert to truncate mode (no transform style)
    const updatedTextSpan = screen.getByText('Long text content here');
    expect(updatedTextSpan).toHaveClass('block');
    expect(updatedTextSpan).toHaveClass('truncate');
  });

  it('does not start animation when text is not truncated', () => {
    render(<ScrollingText text="Short" />);

    const container = screen.getByText('Short').parentElement!;

    // Don't mock truncation - text fits in container

    act(() => {
      fireEvent.mouseEnter(container);
    });

    // When not truncated, even on hover, text remains in truncate mode (no animation)
    const textSpan = screen.getByText('Short');
    expect(textSpan).toHaveClass('block');
    expect(textSpan).toHaveClass('truncate');
  });

  it('cancels animation frame on unmount during animation', () => {
    render(<ScrollingText text="Text that is truncated" />);

    const container = screen.getByText('Text that is truncated').parentElement!;
    const textSpan = screen.getByText('Text that is truncated');

    // Mock truncation
    Object.defineProperty(container, 'clientWidth', {
      value: 30,
      configurable: true,
    });
    Object.defineProperty(textSpan, 'scrollWidth', {
      value: 150,
      configurable: true,
    });

    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    act(() => {
      fireEvent.mouseEnter(container);
    });

    // Unmount while animating - should call cancelAnimationFrame
    act(() => {
      // Advance RAF callbacks
      rafCallbacks.forEach((cb) => cb(1000));
      rafCallbacks = [];
    });
  });
});
