import { render, fireEvent, act } from '@testing-library/react';
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

// Helper to get the container div
const getContainer = () => {
  const containers = document.querySelectorAll('.overflow-hidden');
  return containers[0] as HTMLElement;
};

// Helper to get the measurement span (the one with position: absolute)
const getMeasurementSpan = () => {
  const spans = document.querySelectorAll('span.inline-block');
  for (const span of spans) {
    if ((span as HTMLElement).style.position === 'absolute') {
      return span as HTMLElement;
    }
  }
  // If no absolute span, return the first span (during animation)
  return spans[0] as HTMLElement;
};

// Helper to get the visible text content (when not animating, it's direct text; when animating, it's in a span)
const getVisibleContent = () => {
  const container = getContainer();
  // Get all text content except from the hidden measurement span
  const measSpan = getMeasurementSpan();
  if (measSpan?.style.visibility === 'hidden') {
    // Not animating - text is direct child
    return container.textContent?.replace(measSpan.textContent || '', '') || '';
  }
  // Animating - text is in visible span
  return container.textContent || '';
};

describe('ScrollingText', () => {
  it('renders text content', () => {
    render(<ScrollingText text="Hello World" />);
    expect(getVisibleContent()).toContain('Hello World');
  });

  it('applies custom className', () => {
    render(<ScrollingText text="Test" className="custom-class" />);
    const container = getContainer();
    expect(container).toHaveClass('custom-class');
  });

  it('shows title attribute when truncated', () => {
    render(<ScrollingText text="Long text that should be truncated" />);

    const container = getContainer();
    const textSpan = getMeasurementSpan();

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
    const container = getContainer();
    // Title should not be set when not truncated
    expect(container).not.toHaveAttribute('title');
  });

  it('responds to mouse enter and leave', () => {
    render(<ScrollingText text="Test content" />);
    const container = getContainer();

    fireEvent.mouseEnter(container);
    fireEvent.mouseLeave(container);

    // Component should not throw and should render correctly
    expect(getVisibleContent()).toContain('Test content');
  });

  it('uses custom delay when provided', () => {
    render(<ScrollingText text="Test" delayMs={3000} />);
    expect(getVisibleContent()).toContain('Test');
  });

  it('uses custom speed when provided', () => {
    render(<ScrollingText text="Test" speedPxPerSecond={50} />);
    expect(getVisibleContent()).toContain('Test');
  });

  it('uses custom title when provided', () => {
    render(<ScrollingText text="Short" title="Custom title" />);
    const container = getContainer();
    const textSpan = getMeasurementSpan();

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
    const container = getContainer();
    expect(container).toHaveClass('overflow-hidden');
    expect(container).toHaveClass('whitespace-nowrap');
  });

  it('measurement span has inline-block class', () => {
    render(<ScrollingText text="Test" />);
    const textSpan = getMeasurementSpan();
    expect(textSpan).toHaveClass('inline-block');
  });

  it('cleans up animation frame on unmount', () => {
    const { unmount } = render(<ScrollingText text="Test" />);
    unmount();
    // Should not throw
  });

  it('handles empty text', () => {
    render(<ScrollingText text="" />);
    // Should render without errors
    const container = getContainer();
    expect(container).toBeInTheDocument();
  });

  it('handles very long text', () => {
    const longText = 'A'.repeat(1000);
    render(<ScrollingText text={longText} />);
    expect(getVisibleContent()).toContain(longText);
  });

  it('shows ellipsis when truncated and not hovering', () => {
    render(<ScrollingText text="Long text here" />);
    const container = getContainer();
    const textSpan = getMeasurementSpan();

    // Mock truncation
    Object.defineProperty(container, 'clientWidth', {
      value: 50,
      configurable: true,
    });
    Object.defineProperty(textSpan, 'scrollWidth', {
      value: 200,
      configurable: true,
    });

    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    // Should have ellipsis style when truncated
    expect(container.style.textOverflow).toBe('ellipsis');
  });
});

describe('ScrollingText animation behavior', () => {
  it('starts animation on hover when truncated', () => {
    render(
      <ScrollingText text="This is a long text that should be truncated" />
    );

    const container = getContainer();
    const textSpan = getMeasurementSpan();

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
  });

  it('stops animation on mouse leave', () => {
    render(<ScrollingText text="Long text content here" />);

    const container = getContainer();
    const textSpan = getMeasurementSpan();

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

    // After mouse leave, animation should be cancelled
    // Get the visible span after leave
    const visibleSpan = getMeasurementSpan();
    // Transform should reset to 0 (or no transform in non-animating state)
    expect(visibleSpan.style.transform).toBeFalsy();
  });

  it('does not start animation when text is not truncated', () => {
    render(<ScrollingText text="Short" />);

    const container = getContainer();

    // Don't mock truncation - text fits in container
    (global.requestAnimationFrame as jest.Mock).mockClear();

    act(() => {
      fireEvent.mouseEnter(container);
    });

    // requestAnimationFrame should not be called for animation
    // (may be called for other reasons, but not for scrolling)
    const rafCalls = (global.requestAnimationFrame as jest.Mock).mock.calls
      .length;
    // With no truncation, hovering shouldn't start animation
    expect(rafCalls).toBe(0);
  });

  it('cancels animation frame on unmount during animation', () => {
    const { unmount } = render(<ScrollingText text="Text that is truncated" />);

    const container = getContainer();
    const textSpan = getMeasurementSpan();

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

    // Unmount while animating
    unmount();

    // Should call cancelAnimationFrame
    expect(global.cancelAnimationFrame).toHaveBeenCalled();
  });

  it('switches to scrolling span when hovering on truncated text', () => {
    render(<ScrollingText text="Long text that needs scrolling" />);

    const container = getContainer();
    const initialSpan = getMeasurementSpan();

    // Mock truncation
    Object.defineProperty(container, 'clientWidth', {
      value: 50,
      configurable: true,
    });
    Object.defineProperty(initialSpan, 'scrollWidth', {
      value: 200,
      configurable: true,
    });

    act(() => {
      window.dispatchEvent(new Event('resize'));
    });

    // Before hover - should have hidden measurement span
    expect(initialSpan.style.visibility).toBe('hidden');

    // Hover
    act(() => {
      fireEvent.mouseEnter(container);
    });

    // During hover on truncated text - should switch to visible span for animation
    const animatingSpan = document.querySelector(
      'span.inline-block:not([style*="visibility"])'
    );
    expect(animatingSpan).toBeInTheDocument();
  });
});
