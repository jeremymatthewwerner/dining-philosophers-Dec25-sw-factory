/**
 * Tests for ResizeDivider component.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ResizeDivider } from '../ResizeDivider';

describe('ResizeDivider', () => {
  const mockOnResize = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the resize divider', () => {
    render(<ResizeDivider onResize={mockOnResize} />);

    const divider = screen.getByTestId('resize-divider');
    expect(divider).toBeInTheDocument();
    expect(divider).toHaveAttribute('role', 'separator');
    expect(divider).toHaveAttribute('aria-orientation', 'vertical');
    expect(divider).toHaveAttribute('aria-label', 'Resize sidebar');
  });

  it('has col-resize cursor style', () => {
    render(<ResizeDivider onResize={mockOnResize} />);

    const divider = screen.getByTestId('resize-divider');
    expect(divider).toHaveClass('cursor-col-resize');
  });

  it('is hidden on mobile (lg:flex class)', () => {
    render(<ResizeDivider onResize={mockOnResize} />);

    const divider = screen.getByTestId('resize-divider');
    expect(divider).toHaveClass('hidden');
    expect(divider).toHaveClass('lg:flex');
  });

  it('calls onResize when dragging', () => {
    render(
      <ResizeDivider onResize={mockOnResize} minWidth={200} maxWidth={500} />
    );

    const divider = screen.getByTestId('resize-divider');

    // Start dragging
    fireEvent.mouseDown(divider, { clientX: 288 });

    // Move mouse
    fireEvent.mouseMove(document, { clientX: 350 });

    expect(mockOnResize).toHaveBeenCalledWith(350);
  });

  it('respects minimum width constraint', () => {
    render(
      <ResizeDivider onResize={mockOnResize} minWidth={200} maxWidth={500} />
    );

    const divider = screen.getByTestId('resize-divider');

    // Start dragging
    fireEvent.mouseDown(divider, { clientX: 288 });

    // Move mouse to position below minimum
    fireEvent.mouseMove(document, { clientX: 100 });

    expect(mockOnResize).toHaveBeenCalledWith(200);
  });

  it('respects maximum width constraint', () => {
    render(
      <ResizeDivider onResize={mockOnResize} minWidth={200} maxWidth={500} />
    );

    const divider = screen.getByTestId('resize-divider');

    // Start dragging
    fireEvent.mouseDown(divider, { clientX: 288 });

    // Move mouse to position above maximum
    fireEvent.mouseMove(document, { clientX: 600 });

    expect(mockOnResize).toHaveBeenCalledWith(500);
  });

  it('uses default min/max values when not specified', () => {
    render(<ResizeDivider onResize={mockOnResize} />);

    const divider = screen.getByTestId('resize-divider');

    // Start dragging
    fireEvent.mouseDown(divider, { clientX: 288 });

    // Move below default minimum (200)
    fireEvent.mouseMove(document, { clientX: 100 });
    expect(mockOnResize).toHaveBeenCalledWith(200);

    mockOnResize.mockClear();

    // Move above default maximum (500)
    fireEvent.mouseMove(document, { clientX: 600 });
    expect(mockOnResize).toHaveBeenCalledWith(500);
  });

  it('stops calling onResize after mouseup', () => {
    render(
      <ResizeDivider onResize={mockOnResize} minWidth={200} maxWidth={500} />
    );

    const divider = screen.getByTestId('resize-divider');

    // Start dragging
    fireEvent.mouseDown(divider, { clientX: 288 });

    // Move mouse
    fireEvent.mouseMove(document, { clientX: 350 });
    expect(mockOnResize).toHaveBeenCalledTimes(1);

    // Stop dragging
    fireEvent.mouseUp(document);

    mockOnResize.mockClear();

    // Move mouse again - should NOT trigger onResize
    fireEvent.mouseMove(document, { clientX: 400 });
    expect(mockOnResize).not.toHaveBeenCalled();
  });

  it('does not call onResize on mousemove without mousedown', () => {
    render(
      <ResizeDivider onResize={mockOnResize} minWidth={200} maxWidth={500} />
    );

    // Move mouse without starting drag
    fireEvent.mouseMove(document, { clientX: 350 });

    expect(mockOnResize).not.toHaveBeenCalled();
  });

  it('prevents default on mousedown to avoid text selection', () => {
    render(<ResizeDivider onResize={mockOnResize} />);

    const divider = screen.getByTestId('resize-divider');
    const preventDefault = jest.fn();

    // Create a mouse event with preventDefault mock
    const event = new MouseEvent('mousedown', { bubbles: true });
    Object.defineProperty(event, 'preventDefault', { value: preventDefault });

    divider.dispatchEvent(event);

    expect(preventDefault).toHaveBeenCalled();
  });

  it('sets body cursor style to col-resize during drag', () => {
    render(<ResizeDivider onResize={mockOnResize} />);

    const divider = screen.getByTestId('resize-divider');

    // Initially body should not have col-resize cursor
    expect(document.body.style.cursor).not.toBe('col-resize');

    // Start dragging
    fireEvent.mouseDown(divider, { clientX: 288 });

    // Body should have col-resize cursor
    expect(document.body.style.cursor).toBe('col-resize');

    // Stop dragging
    fireEvent.mouseUp(document);

    // Body cursor should be reset
    expect(document.body.style.cursor).toBe('');
  });

  it('disables text selection during drag', () => {
    render(<ResizeDivider onResize={mockOnResize} />);

    const divider = screen.getByTestId('resize-divider');

    // Initially body should allow text selection
    expect(document.body.style.userSelect).not.toBe('none');

    // Start dragging
    fireEvent.mouseDown(divider, { clientX: 288 });

    // Body should disable text selection
    expect(document.body.style.userSelect).toBe('none');

    // Stop dragging
    fireEvent.mouseUp(document);

    // Body userSelect should be reset
    expect(document.body.style.userSelect).toBe('');
  });

  it('adds active class when dragging', () => {
    render(<ResizeDivider onResize={mockOnResize} />);

    const divider = screen.getByTestId('resize-divider');

    // Start dragging
    fireEvent.mouseDown(divider, { clientX: 288 });

    // Should have active class
    expect(divider).toHaveClass('bg-blue-500');

    // Stop dragging
    fireEvent.mouseUp(document);

    // Active class should be removed (just the normal bg-zinc class)
    expect(divider).not.toHaveClass('bg-blue-500');
  });
});
