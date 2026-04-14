/**
 * Tests for StatusLine component.
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
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

    // Wait for fetch to complete AND state to settle — combined assertion avoids
    // arbitrary setTimeout delays that are slow and brittle under CI load.
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
      // Element must remain absent after state settles (stale-complete shows nothing)
      expect(container.querySelector('[data-testid="status-line"]')).toBeNull();
    });
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

    // Wait for fetch attempt AND state to settle — combined assertion avoids
    // arbitrary setTimeout delays that are slow and brittle under CI load.
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
      // On fetch error, fetchThinkerStatus returns null, statuses stays empty,
      // component renders nothing — verify element is absent after state settles.
      expect(container.querySelector('[data-testid="status-line"]')).toBeNull();
    });
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

  // Regression tests for issue #114 - polling lifecycle fixes
  describe('Polling lifecycle (regression #114)', () => {
    let setIntervalSpy: jest.SpyInstance;
    let clearIntervalSpy: jest.SpyInstance;
    let intervals: NodeJS.Timeout[] = [];

    beforeEach(() => {
      intervals = [];
      setIntervalSpy = jest.spyOn(global, 'setInterval').mockImplementation(((
        callback: () => void,
        ms: number
      ) => {
        const intervalId = {
          _id: Math.random(),
          callback,
          ms,
        } as unknown as NodeJS.Timeout;
        intervals.push(intervalId);
        return intervalId;
      }) as typeof setInterval);

      clearIntervalSpy = jest
        .spyOn(global, 'clearInterval')
        .mockImplementation(((id: NodeJS.Timeout) => {
          intervals = intervals.filter((i) => i !== id);
        }) as typeof clearInterval);
    });

    afterEach(() => {
      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    });

    it('starts polling when component mounts with thinkers', async () => {
      mockFetch.mockResolvedValue({
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
        <StatusLine
          thinkerNames={['Socrates']}
          apiBaseUrl="http://test.com"
          pollInterval={5000}
        />
      );

      // Initial fetch on mount
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(1);
      });

      // setInterval should have been called to set up polling
      expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 5000);
      expect(intervals.length).toBe(1);
    });

    it('stops polling when component unmounts', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'Socrates',
            status: 'pending',
            has_data: false,
            updated_at: new Date().toISOString(),
          }),
      });

      const { unmount } = render(
        <StatusLine
          thinkerNames={['Socrates']}
          apiBaseUrl="http://test.com"
          pollInterval={5000}
        />
      );

      // Initial fetch on mount
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(1);
      });

      // setInterval should have been called
      expect(setIntervalSpy).toHaveBeenCalled();
      const intervalCountBeforeUnmount = intervals.length;
      expect(intervalCountBeforeUnmount).toBe(1);

      // Unmount the component
      unmount();

      // clearInterval should have been called to clean up
      expect(clearIntervalSpy).toHaveBeenCalled();
      expect(intervals.length).toBe(0);
    });

    it('restarts polling when thinker list changes', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'Socrates',
            status: 'pending',
            has_data: false,
            updated_at: new Date().toISOString(),
          }),
      });

      const { rerender } = render(
        <StatusLine
          thinkerNames={['Socrates']}
          apiBaseUrl="http://test.com"
          pollInterval={5000}
        />
      );

      // Initial fetch on mount
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(1);
      });

      // setInterval should have been called - get the first interval ID
      const callCountBeforeRerender = setIntervalSpy.mock.calls.length;
      expect(callCountBeforeRerender).toBeGreaterThanOrEqual(1);
      const firstIntervalId = intervals[0];

      // Update thinker list - should trigger immediate fetch and restart polling
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'Aristotle',
            status: 'pending',
            has_data: false,
            updated_at: new Date().toISOString(),
          }),
      });

      rerender(
        <StatusLine
          thinkerNames={['Aristotle']}
          apiBaseUrl="http://test.com"
          pollInterval={5000}
        />
      );

      // Should have made a new fetch call for the new thinker
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(2);
      });

      // Old interval should have been cleared and new one created
      await waitFor(() => {
        expect(clearIntervalSpy).toHaveBeenCalledWith(firstIntervalId);
        // setInterval should have been called more times than before rerender
        expect(setIntervalSpy.mock.calls.length).toBeGreaterThan(
          callCountBeforeRerender
        );
      });

      // Should have one active interval (old cleared, new created)
      expect(intervals.length).toBe(1);
      expect(intervals[0]).not.toBe(firstIntervalId);
    });

    it('continues polling even when fetch takes time (regression #187)', async () => {
      // Regression test for issue #187: When isPolling was a state variable in
      // useCallback dependencies, the callback could be recreated with isPolling=true
      // baked in, causing subsequent interval callbacks to skip fetching.

      // Simulate a slow fetch that returns complete after first call
      let fetchCount = 0;
      mockFetch.mockImplementation(() => {
        fetchCount++;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              name: 'Socrates',
              status: fetchCount === 1 ? 'in_progress' : 'complete',
              has_data: fetchCount > 1,
              updated_at: new Date().toISOString(),
            }),
        });
      });

      render(
        <StatusLine
          thinkerNames={['Socrates']}
          apiBaseUrl="http://test.com"
          pollInterval={50}
        />
      );

      // Wait for initial fetch to complete AND component to re-render with
      // the in_progress status. The re-render only happens after setStatuses()
      // resolves, which is in the same microtask as isPollingRef.current = false
      // (finally block). Waiting for the DOM update guarantees isPollingRef is
      // false, avoiding the arbitrary 50ms setTimeout previously used here.
      await waitFor(() => {
        expect(screen.getByTestId('active-research')).toBeInTheDocument();
      });

      // The test spies on setInterval above but doesn't fire actual intervals.
      // To verify the callback works correctly after fetch completes, manually
      // trigger the interval callback and check that it can fetch again.
      const intervalCallback = intervals[0] as unknown as {
        callback: () => void;
      };

      // Trigger the interval callback - isPollingRef is guaranteed false now
      // (ref resets in the finally block before React processes the re-render)
      await act(async () => {
        intervalCallback.callback();
        // Flush microtasks so the async fetch chain completes inside act
        await Promise.resolve();
        await Promise.resolve();
      });

      // The key assertion: The second fetch should have been triggered,
      // proving that the ref-based polling guard works correctly
      // (unlike the old state-based approach which could get stuck)
      expect(fetchCount).toBeGreaterThanOrEqual(2);
    });
  });
});
