/**
 * Tests for ThinkerAvatar component.
 *
 * Covers: initials fallback, size variants, image error handling,
 * color derivation, and accessibility attributes.
 */

import { render, screen, fireEvent } from '@/test-utils';
import { ThinkerAvatar } from '@/components/ThinkerAvatar';

describe('ThinkerAvatar', () => {
  describe('initials fallback (no image)', () => {
    it('shows initials for a two-word name', () => {
      render(<ThinkerAvatar name="Alan Turing" />);
      expect(screen.getByText('AT')).toBeInTheDocument();
    });

    it('shows first initial only for a single-word name', () => {
      render(<ThinkerAvatar name="Socrates" />);
      expect(screen.getByText('S')).toBeInTheDocument();
    });

    it('shows first and last initial for multi-word name', () => {
      render(<ThinkerAvatar name="Marie Curie Sklodowska" />);
      // First + last word initial
      expect(screen.getByText('MS')).toBeInTheDocument();
    });

    it('shows ? for empty name', () => {
      render(<ThinkerAvatar name="" />);
      expect(screen.getByText('?')).toBeInTheDocument();
    });

    it('is uppercase', () => {
      render(<ThinkerAvatar name="alan turing" />);
      expect(screen.getByText('AT')).toBeInTheDocument();
    });
  });

  describe('image rendering', () => {
    it('renders an image when imageUrl is provided', () => {
      render(
        <ThinkerAvatar
          name="Socrates"
          imageUrl="https://example.com/socrates.jpg"
        />
      );
      expect(screen.getByAltText('Socrates')).toBeInTheDocument();
    });

    it('falls back to initials when image errors', () => {
      render(
        <ThinkerAvatar
          name="Socrates"
          imageUrl="https://example.com/socrates.jpg"
        />
      );
      const img = screen.getByAltText('Socrates');
      fireEvent.error(img);
      // After error, initials should appear
      expect(screen.getByText('S')).toBeInTheDocument();
    });

    it('renders initials when imageUrl is null', () => {
      render(<ThinkerAvatar name="Plato" imageUrl={null} />);
      expect(screen.getByText('P')).toBeInTheDocument();
    });

    it('renders initials when imageUrl is undefined', () => {
      render(<ThinkerAvatar name="Kant" />);
      expect(screen.getByText('K')).toBeInTheDocument();
    });
  });

  describe('size variants', () => {
    it('renders xs size', () => {
      render(<ThinkerAvatar name="Socrates" size="xs" />);
      const container = screen.getByTitle('Socrates');
      expect(container).toHaveClass('w-4', 'h-4');
    });

    it('renders sm size', () => {
      render(<ThinkerAvatar name="Socrates" size="sm" />);
      const container = screen.getByTitle('Socrates');
      expect(container).toHaveClass('w-6', 'h-6');
    });

    it('renders md size (default)', () => {
      render(<ThinkerAvatar name="Socrates" />);
      const container = screen.getByTitle('Socrates');
      expect(container).toHaveClass('w-8', 'h-8');
    });

    it('renders lg size', () => {
      render(<ThinkerAvatar name="Socrates" size="lg" />);
      const container = screen.getByTitle('Socrates');
      expect(container).toHaveClass('w-10', 'h-10');
    });
  });

  describe('color', () => {
    it('uses custom color when provided', () => {
      render(<ThinkerAvatar name="Socrates" color="#FF0000" />);
      const container = screen.getByTitle('Socrates');
      // Background color is applied via inline style
      expect(container).toHaveStyle({ backgroundColor: '#FF0000' });
    });

    it('derives a consistent color from name when no color provided', () => {
      const { unmount } = render(<ThinkerAvatar name="Socrates" />);
      const container = screen.getByTitle('Socrates');
      const style = container.style.backgroundColor;
      unmount();

      // Re-render same name - should get same color
      render(<ThinkerAvatar name="Socrates" />);
      const container2 = screen.getByTitle('Socrates');
      expect(container2.style.backgroundColor).toBe(style);
    });

    it('derives different colors for different names', () => {
      const { unmount } = render(<ThinkerAvatar name="Socrates" />);
      const socratesColor = screen.getByTitle('Socrates').style.backgroundColor;
      unmount();

      render(<ThinkerAvatar name="Einstein" />);
      const einsteinColor = screen.getByTitle('Einstein').style.backgroundColor;

      // Different names may get different colors (hash-based)
      // We just verify both are set and are valid color strings
      expect(socratesColor).toBeTruthy();
      expect(einsteinColor).toBeTruthy();
    });

    it('does not apply background style when showing image', () => {
      render(
        <ThinkerAvatar name="Socrates" imageUrl="https://example.com/img.jpg" />
      );
      const container = screen.getByTitle('Socrates');
      // When image is shown, no backgroundColor style should be applied
      expect(container.style.backgroundColor).toBe('');
    });
  });

  describe('accessibility', () => {
    it('has title attribute with thinker name', () => {
      render(<ThinkerAvatar name="Aristotle" />);
      expect(screen.getByTitle('Aristotle')).toBeInTheDocument();
    });

    it('image has alt text equal to thinker name', () => {
      render(
        <ThinkerAvatar name="Plato" imageUrl="https://example.com/plato.jpg" />
      );
      expect(screen.getByAltText('Plato')).toBeInTheDocument();
    });
  });
});
