/**
 * Tests for BuildInfo component
 */

import { render } from '@testing-library/react';
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
        'Dining Philosophers - Build: 2025-12-18T08:00:00.000Z'
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

  it('should not render any visible content', () => {
    const { container } = render(<BuildInfo />);
    expect(container.firstChild).toBeNull();
  });
});
