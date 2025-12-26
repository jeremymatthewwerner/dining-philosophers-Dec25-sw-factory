/**
 * Tests for BuildInfo component
 */

import { render, screen } from '@testing-library/react';
import { BuildInfo } from '../BuildInfo';

describe('BuildInfo', () => {
  let consoleLogSpy: jest.SpyInstance;

  beforeEach(() => {
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
  });

  it('should render without crashing', () => {
    const { container } = render(<BuildInfo />);
    expect(container).toBeInTheDocument();
  });

  it('should log build time when NEXT_PUBLIC_BUILD_TIME is set', () => {
    const originalEnv = process.env.NEXT_PUBLIC_BUILD_TIME;
    process.env.NEXT_PUBLIC_BUILD_TIME = '2025-12-18T08:00:00.000Z';

    render(<BuildInfo />);

    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining(
        'dining philosophers - Build: 2025-12-18T08:00:00.000Z'
      ),
      expect.any(String)
    );

    // Restore original env
    process.env.NEXT_PUBLIC_BUILD_TIME = originalEnv;
  });

  it('should not log when NEXT_PUBLIC_BUILD_TIME is not set', () => {
    const originalEnv = process.env.NEXT_PUBLIC_BUILD_TIME;
    delete process.env.NEXT_PUBLIC_BUILD_TIME;

    render(<BuildInfo />);

    expect(consoleLogSpy).not.toHaveBeenCalled();

    // Restore original env
    process.env.NEXT_PUBLIC_BUILD_TIME = originalEnv;
  });

  it('should render formatted build timestamp when NEXT_PUBLIC_BUILD_TIME is set', () => {
    const originalEnv = process.env.NEXT_PUBLIC_BUILD_TIME;
    process.env.NEXT_PUBLIC_BUILD_TIME = '2025-12-26T13:05:00.000Z';

    render(<BuildInfo />);

    const buildInfo = screen.getByTestId('build-info');
    expect(buildInfo).toBeInTheDocument();
    expect(buildInfo).toHaveTextContent(/Built:/);
    // Check that it contains formatted date parts (format depends on locale)
    expect(buildInfo.textContent).toMatch(/Built:/);

    // Restore original env
    process.env.NEXT_PUBLIC_BUILD_TIME = originalEnv;
  });

  it('should not render any visible content when NEXT_PUBLIC_BUILD_TIME is not set', () => {
    const originalEnv = process.env.NEXT_PUBLIC_BUILD_TIME;
    delete process.env.NEXT_PUBLIC_BUILD_TIME;

    const { container } = render(<BuildInfo />);
    expect(container.firstChild).toBeNull();

    // Restore original env
    process.env.NEXT_PUBLIC_BUILD_TIME = originalEnv;
  });

  it('should format timestamp in the expected format', () => {
    const originalEnv = process.env.NEXT_PUBLIC_BUILD_TIME;
    // Set a specific timestamp
    process.env.NEXT_PUBLIC_BUILD_TIME = '2025-12-26T13:05:00.000Z';

    render(<BuildInfo />);

    const buildInfo = screen.getByTestId('build-info');
    // The format should be like "Built: Dec 26, 2025 at 1:05 PM"
    // We'll check for the presence of key parts rather than exact match due to locale differences
    expect(buildInfo.textContent).toMatch(/Built:/);
    expect(buildInfo.textContent).toMatch(/at/);

    // Restore original env
    process.env.NEXT_PUBLIC_BUILD_TIME = originalEnv;
  });

  it('should format timestamp with comma after day and before year', () => {
    const originalEnv = process.env.NEXT_PUBLIC_BUILD_TIME;
    // Set a specific timestamp: Dec 26, 2025 at 6:14 PM
    process.env.NEXT_PUBLIC_BUILD_TIME = '2025-12-26T18:14:00.000Z';

    render(<BuildInfo />);

    const buildInfo = screen.getByTestId('build-info');
    const text = buildInfo.textContent || '';

    // Should contain "Dec 26, 2025 at" with comma after day
    // The exact format: "Built: Dec 26, 2025 at 6:14 PM"
    expect(text).toMatch(/Dec \d+, \d{4} at \d+:\d+ [AP]M/);

    // More specifically, should NOT be "Dec 26 at 2025" (the bug)
    expect(text).not.toMatch(/Dec \d+ at \d{4}/);

    // Restore original env
    process.env.NEXT_PUBLIC_BUILD_TIME = originalEnv;
  });
});
