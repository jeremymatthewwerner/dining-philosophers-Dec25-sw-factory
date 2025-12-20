/**
 * Tests for bug report URL generation
 */

import { generateBugReportUrl } from '../bugReport';

describe('generateBugReportUrl', () => {
  // Mock navigator.userAgent
  const originalNavigator = global.navigator;

  beforeEach(() => {
    // Mock Chrome on Windows
    Object.defineProperty(global, 'navigator', {
      value: {
        userAgent:
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(global, 'navigator', {
      value: originalNavigator,
      writable: true,
      configurable: true,
    });
  });

  it('generates URL with username only', () => {
    const url = generateBugReportUrl({ username: 'testuser' });

    expect(url).toContain(
      'https://github.com/jeremymatthewwerner/thinkers-chat/issues/new'
    );
    expect(url).toContain('title=');
    expect(url).toContain('labels=P3');

    // Decode the URL to check content
    const decodedUrl = decodeURIComponent(url);
    expect(decodedUrl).toContain('Filed from thinkers-chat app by testuser');
    expect(decodedUrl).toContain('Username: testuser');
    expect(decodedUrl).toContain('Chrome');
    expect(decodedUrl).toContain('Windows');
  });

  it('generates URL with username and display name', () => {
    const url = generateBugReportUrl({
      username: 'testuser',
      displayName: 'Test User',
    });

    const decodedUrl = decodeURIComponent(url);
    expect(decodedUrl).toContain('Filed from thinkers-chat app by Test User');
    expect(decodedUrl).toContain('Username: testuser');
    expect(decodedUrl).toContain('Display Name: Test User');
  });

  it('handles missing username gracefully', () => {
    const url = generateBugReportUrl({});

    const decodedUrl = decodeURIComponent(url);
    expect(decodedUrl).toContain(
      'Filed from thinkers-chat app by Unknown User'
    );
    expect(decodedUrl).toContain('Username: Not available');
  });

  it('includes browser and OS information', () => {
    const url = generateBugReportUrl({ username: 'testuser' });

    const decodedUrl = decodeURIComponent(url);
    expect(decodedUrl).toContain('Browser: Chrome');
    expect(decodedUrl).toContain('OS: Windows');
    expect(decodedUrl).toContain('User Agent:');
  });

  it('includes all required sections in the body', () => {
    const url = generateBugReportUrl({ username: 'testuser' });

    const decodedUrl = decodeURIComponent(url);
    expect(decodedUrl).toContain('## Description');
    expect(decodedUrl).toContain('## Steps to Reproduce');
    expect(decodedUrl).toContain('## Expected Behavior');
    expect(decodedUrl).toContain('## Actual Behavior');
    expect(decodedUrl).toContain('## Browser/Device');
  });

  describe('browser detection', () => {
    it('detects Firefox', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        },
        writable: true,
        configurable: true,
      });

      const url = generateBugReportUrl({ username: 'testuser' });
      const decodedUrl = decodeURIComponent(url);
      expect(decodedUrl).toContain('Browser: Firefox');
    });

    it('detects Edge', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        },
        writable: true,
        configurable: true,
      });

      const url = generateBugReportUrl({ username: 'testuser' });
      const decodedUrl = decodeURIComponent(url);
      expect(decodedUrl).toContain('Browser: Edge');
    });

    it('detects Safari', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        },
        writable: true,
        configurable: true,
      });

      const url = generateBugReportUrl({ username: 'testuser' });
      const decodedUrl = decodeURIComponent(url);
      expect(decodedUrl).toContain('Browser: Safari');
    });
  });

  describe('OS detection', () => {
    it('detects macOS', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        writable: true,
        configurable: true,
      });

      const url = generateBugReportUrl({ username: 'testuser' });
      const decodedUrl = decodeURIComponent(url);
      expect(decodedUrl).toContain('OS: macOS');
    });

    it('detects Linux', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        writable: true,
        configurable: true,
      });

      const url = generateBugReportUrl({ username: 'testuser' });
      const decodedUrl = decodeURIComponent(url);
      expect(decodedUrl).toContain('OS: Linux');
    });

    it('detects Android', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        },
        writable: true,
        configurable: true,
      });

      const url = generateBugReportUrl({ username: 'testuser' });
      const decodedUrl = decodeURIComponent(url);
      expect(decodedUrl).toContain('OS: Android');
    });

    it('detects iOS', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        },
        writable: true,
        configurable: true,
      });

      const url = generateBugReportUrl({ username: 'testuser' });
      const decodedUrl = decodeURIComponent(url);
      expect(decodedUrl).toContain('OS: iOS');
    });
  });

  it('handles undefined navigator gracefully', () => {
    Object.defineProperty(global, 'navigator', {
      value: undefined,
      writable: true,
      configurable: true,
    });

    const url = generateBugReportUrl({ username: 'testuser' });
    const decodedUrl = decodeURIComponent(url);
    expect(decodedUrl).toContain('Browser: Unknown Browser');
    expect(decodedUrl).toContain('OS: Unknown OS');
    expect(decodedUrl).toContain('User Agent: `Unknown`');
  });
});
