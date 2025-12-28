/**
 * Tests for StatusLine component.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { StatusLine } from '../StatusLine';

// Mock the LanguageContext
jest.mock('@/contexts/LanguageContext', () => ({
  useLanguage: () => ({
    t: {
      statusLine: {
        researching: 'Researching background information...',
        researchComplete: 'Background research complete',
        researchFailed: 'Could not load background research',
        cacheHit: 'Using cached research data',
      },
    },
  }),
}));

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(() => 'test-token'),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

describe('StatusLine', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders nothing when thinkerNames is empty', () => {
    const { container } = render(
      <StatusLine thinkerNames={[]} apiBaseUrl="http://test.com" />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when visible is false', () => {
    const { container } = render(
      <StatusLine
        thinkerNames={['Socrates']}
        apiBaseUrl="http://test.com"
        visible={false}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('shows active research indicator when research is in progress', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          name: 'Socrates',
          status: 'in_progress',
          has_data: false,
          updated_at: new Date().toISOString(),
        }),
    });

    render(
      <StatusLine thinkerNames={['Socrates']} apiBaseUrl="http://test.com" />
    );

    await waitFor(
      () => {
        expect(screen.getByTestId('active-research')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(
      screen.getByText('Researching background information...')
    ).toBeInTheDocument();
    expect(screen.getByText('(Socrates)')).toBeInTheDocument();
  });

  it('shows research complete indicator when research recently completed', async () => {
    // Research completed 10 seconds ago (within 30 second window)
    const tenSecondsAgo = new Date(Date.now() - 10000).toISOString();

    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          name: 'Aristotle',
          status: 'complete',
          has_data: true,
          updated_at: tenSecondsAgo,
        }),
    });

    render(
      <StatusLine thinkerNames={['Aristotle']} apiBaseUrl="http://test.com" />
    );

    await waitFor(
      () => {
        expect(screen.getByTestId('research-complete')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(
      screen.getByText('Background research complete')
    ).toBeInTheDocument();
  });

  it('shows research failed indicator when research failed', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          name: 'Plato',
          status: 'failed',
          has_data: false,
          updated_at: new Date().toISOString(),
        }),
    });

    render(
      <StatusLine thinkerNames={['Plato']} apiBaseUrl="http://test.com" />
    );

    await waitFor(
      () => {
        expect(screen.getByTestId('research-failed')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(
      screen.getByText('Could not load background research')
    ).toBeInTheDocument();
  });

  it('renders nothing when research is complete but not recent', async () => {
    // Research completed 5 minutes ago (outside 30 second window)
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();

    // Use mockImplementation to ensure it returns the same value on every call
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'Confucius',
            status: 'complete',
            has_data: true,
            updated_at: fiveMinutesAgo,
          }),
      })
    );

    const { container } = render(
      <StatusLine thinkerNames={['Confucius']} apiBaseUrl="http://test.com" />
    );

    // Wait for fetch to complete
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });

    // Wait a moment for state to settle
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should not show status line since nothing interesting is happening
    expect(container.querySelector('[data-testid="status-line"]')).toBeNull();
  });

  it('handles multiple thinkers with mixed statuses', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'Socrates',
            status: 'in_progress',
            has_data: false,
            updated_at: new Date().toISOString(),
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'Aristotle',
            status: 'complete',
            has_data: true,
            updated_at: new Date().toISOString(),
          }),
      });

    render(
      <StatusLine
        thinkerNames={['Socrates', 'Aristotle']}
        apiBaseUrl="http://test.com"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('status-line')).toBeInTheDocument();
    });

    // Should show active research (in_progress takes priority)
    await waitFor(() => {
      expect(screen.getByTestId('active-research')).toBeInTheDocument();
    });
  });

  it('handles fetch errors gracefully', async () => {
    // Use mockImplementation to ensure all calls fail
    mockFetch.mockImplementation(() =>
      Promise.reject(new Error('Network error'))
    );

    const { container } = render(
      <StatusLine thinkerNames={['Socrates']} apiBaseUrl="http://test.com" />
    );

    // Wait for fetch to complete
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });

    // Wait a moment for state to settle
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should not crash, just render nothing since status is unknown
    expect(container.querySelector('[data-testid="status-line"]')).toBeNull();
  });

  it('sends auth token with requests', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          name: 'Socrates',
          status: 'pending',
          has_data: false,
          updated_at: new Date().toISOString(),
        }),
    });

    render(
      <StatusLine thinkerNames={['Socrates']} apiBaseUrl="http://test.com" />
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        'http://test.com/api/thinkers/knowledge/Socrates/status',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });
  });
});
