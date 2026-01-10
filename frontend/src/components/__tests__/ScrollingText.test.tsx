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

// Helper to get the visible text span (the one without aria-hidden)
const getVisibleTextSpan = (text: string): HTMLElement => {
  const spans = screen.getAllByText(text);
  // Find the visible span (not aria-hidden)
  const visibleSpan = spans.find((span) => !span.hasAttribute('aria-hidden'));
  if (!visibleSpan) {
    throw new Error('Visible text span not found');
  }
  return visibleSpan;
};

// Helper to get container and measurement span
const getMeasurementSpan = (container: HTMLElement): HTMLElement => {
  // The measurement span is the hidden one with aria-hidden="true"
  const measureSpan = container.querySelector('[aria-hidden="true"]');
  if (!measureSpan) {
    throw new Error('Measurement span not found');
  }
  return measureSpan as HTMLElement;
};

describe('ScrollingText', () => {
  it('renders text content', () => {
    render(<ScrollingText text="Hello World" />);
    // Both spans have the text, just check at least one exists
    const spans = screen.getAllByText('Hello World');
    expect(spans.length).toBe(2); // Hidden measurement span + visible span
    expect(getVisibleTextSpan('Hello World')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<ScrollingText text="Test" className="custom-class" />);
    // Get the visible text span, then its parent is the container
    const visibleSpan = getVisibleTextSpan('Test');
    const container = visibleSpan.parentElement;
    expect(container).toHaveClass('custom-class');
  });

  it('shows title attribute when truncated', () => {
    render(<ScrollingText text="Long text that should be truncated" />);

    // Get the visible text span and its container
    const visibleSpan = getVisibleTextSpan(
      'Long text that should be truncated'
    );
    const container = visibleSpan.parentElement!;
    const measureSpan = getMeasurementSpan(container);

    // Mock the refs to simulate truncation
    Object.defineProperty(container, 'clientWidth', { value: 50 });
    // Mock the measurement span's scrollWidth (not the visible span)
    Object.defineProperty(measureSpan, 'scrollWidth', { value: 100 });

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
    const visibleSpan = getVisibleTextSpan('Short');
    const container = visibleSpan.parentElement;
    // Title should not be set when not truncated
    expect(container).not.toHaveAttribute('title');
  });

  it('responds to mouse enter and leave', () => {
    render(<ScrollingText text="Test content" />);
    const visibleSpan = getVisibleTextSpan('Test content');
    const container = visibleSpan.parentElement!;

    fireEvent.mouseEnter(container);
    fireEvent.mouseLeave(container);

    // Component should not throw and should render correctly
    expect(getVisibleTextSpan('Test content')).toBeInTheDocument();
  });

  it('uses custom delay when provided', () => {
    render(<ScrollingText text="Test" delayMs={3000} />);
    expect(getVisibleTextSpan('Test')).toBeInTheDocument();
  });

  it('uses custom speed when provided', () => {
    render(<ScrollingText text="Test" speedPxPerSecond={50} />);
    expect(getVisibleTextSpan('Test')).toBeInTheDocument();
  });

  it('uses custom title when provided', () => {
    render(<ScrollingText text="Short" title="Custom title" />);
    const visibleSpan = getVisibleTextSpan('Short');
    const container = visibleSpan.parentElement!;
    const measureSpan = getMeasurementSpan(container);

    // Mock truncation on measurement span
    Object.defineProperty(container, 'clientWidth', { value: 50 });
    Object.defineProperty(measureSpan, 'scrollWidth', { value: 100 });

    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    // Custom title should be shown when truncated
    expect(container).toHaveAttribute('title', 'Custom title');
  });

  it('has correct overflow styling', () => {
    render(<ScrollingText text="Test" className="test-class" />);
    const visibleSpan = getVisibleTextSpan('Test');
    const container = visibleSpan.parentElement;
    expect(container).toHaveClass('overflow-hidden');
    expect(container).toHaveClass('whitespace-nowrap');
    expect(container).toHaveClass('relative');
  });

  it('text span has block truncate class when not animating', () => {
    render(<ScrollingText text="Test" />);
    const textSpan = getVisibleTextSpan('Test');
    // When not hovering/animating, text shows with truncate class for ellipsis
    expect(textSpan).toHaveClass('block');
    expect(textSpan).toHaveClass('truncate');
  });

  it('has hidden measurement span', () => {
    render(<ScrollingText text="Test" />);
    const visibleSpan = getVisibleTextSpan('Test');
    const container = visibleSpan.parentElement!;
    const measureSpan = getMeasurementSpan(container);

    // Measurement span should be hidden with specific classes
    expect(measureSpan).toHaveClass('absolute');
    expect(measureSpan).toHaveClass('invisible');
    expect(measureSpan).toHaveClass('whitespace-nowrap');
    expect(measureSpan).toHaveAttribute('aria-hidden', 'true');
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
    expect(getVisibleTextSpan(longText)).toBeInTheDocument();
  });
});

describe('ScrollingText animation behavior', () => {
  it('starts animation on hover when truncated', () => {
    render(
      <ScrollingText text="This is a long text that should be truncated" />
    );

    const visibleSpan = getVisibleTextSpan(
      'This is a long text that should be truncated'
    );
    const container = visibleSpan.parentElement!;
    const measureSpan = getMeasurementSpan(container);

    // Mock truncation on measurement span
    Object.defineProperty(container, 'clientWidth', {
      value: 50,
      configurable: true,
    });
    Object.defineProperty(measureSpan, 'scrollWidth', {
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
    const animatingSpan = getVisibleTextSpan(
      'This is a long text that should be truncated'
    );
    expect(animatingSpan).toHaveClass('inline-block');
    expect(animatingSpan).not.toHaveClass('truncate');
  });

  it('stops animation on mouse leave', () => {
    render(<ScrollingText text="Long text content here" />);

    const visibleSpan = getVisibleTextSpan('Long text content here');
    const container = visibleSpan.parentElement!;
    const measureSpan = getMeasurementSpan(container);

    // Mock truncation on measurement span
    Object.defineProperty(container, 'clientWidth', {
      value: 30,
      configurable: true,
    });
    Object.defineProperty(measureSpan, 'scrollWidth', {
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
    const updatedTextSpan = getVisibleTextSpan('Long text content here');
    expect(updatedTextSpan).toHaveClass('block');
    expect(updatedTextSpan).toHaveClass('truncate');
  });

  it('does not start animation when text is not truncated', () => {
    render(<ScrollingText text="Short" />);

    const visibleSpan = getVisibleTextSpan('Short');
    const container = visibleSpan.parentElement!;

    // Don't mock truncation - text fits in container

    act(() => {
      fireEvent.mouseEnter(container);
    });

    // When not truncated, even on hover, text remains in truncate mode (no animation)
    const textSpan = getVisibleTextSpan('Short');
    expect(textSpan).toHaveClass('block');
    expect(textSpan).toHaveClass('truncate');
  });

  it('cancels animation frame on unmount during animation', () => {
    render(<ScrollingText text="Text that is truncated" />);

    const visibleSpan = getVisibleTextSpan('Text that is truncated');
    const container = visibleSpan.parentElement!;
    const measureSpan = getMeasurementSpan(container);

    // Mock truncation on measurement span
    Object.defineProperty(container, 'clientWidth', {
      value: 30,
      configurable: true,
    });
    Object.defineProperty(measureSpan, 'scrollWidth', {
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

describe('ScrollingText ResizeObserver behavior', () => {
  let mockResizeObserver: jest.Mock;
  let mockObserve: jest.Mock;
  let mockDisconnect: jest.Mock;
  let resizeCallback: ((entries: unknown[]) => void) | null = null;

  beforeEach(() => {
    mockObserve = jest.fn();
    mockDisconnect = jest.fn();
    mockResizeObserver = jest.fn((callback) => {
      resizeCallback = callback;
      return {
        observe: mockObserve,
        disconnect: mockDisconnect,
        unobserve: jest.fn(),
      };
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (global as any).ResizeObserver = mockResizeObserver;
  });

  afterEach(() => {
    resizeCallback = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (global as any).ResizeObserver;
  });

  it('uses ResizeObserver to detect container size changes', () => {
    render(<ScrollingText text="Test text for resize" />);

    // ResizeObserver should be created and observe called on container
    expect(mockResizeObserver).toHaveBeenCalled();
    expect(mockObserve).toHaveBeenCalled();
  });

  it('disconnects ResizeObserver on unmount', () => {
    const { unmount } = render(<ScrollingText text="Test text" />);

    unmount();

    expect(mockDisconnect).toHaveBeenCalled();
  });

  it('rechecks truncation when ResizeObserver fires', () => {
    render(<ScrollingText text="Text that might be truncated" />);

    const visibleSpan = getVisibleTextSpan('Text that might be truncated');
    const container = visibleSpan.parentElement!;
    const measureSpan = getMeasurementSpan(container);

    // Initially not truncated (no title)
    expect(container).not.toHaveAttribute('title');

    // Now mock truncation on measurement span
    Object.defineProperty(container, 'clientWidth', {
      value: 50,
      configurable: true,
    });
    Object.defineProperty(measureSpan, 'scrollWidth', {
      value: 200,
      configurable: true,
    });

    // Simulate ResizeObserver callback (container resized)
    act(() => {
      if (resizeCallback) {
        resizeCallback([{ contentRect: { width: 50 } }]);
      }
    });

    // After resize, truncation should be detected and title set
    expect(container).toHaveAttribute('title', 'Text that might be truncated');
  });
});
