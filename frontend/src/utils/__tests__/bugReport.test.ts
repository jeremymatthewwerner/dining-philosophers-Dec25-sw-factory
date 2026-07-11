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
      'https://github.com/jeremymatthewwerner/dining-philosophers-Dec25-sw-factory/issues/new'
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

  describe('Windows version boundaries (edge cases)', () => {
    // Each Windows NT version maps to a distinct marketing name. These are
    // boundary branches (lines 93-97 of bugReport.ts) that only fire for an
    // exact NT version string — a subtle off-by-one in the version match
    // would misreport the OS without any test noticing.
    const ntCases: Array<[string, string]> = [
      ['10.0', 'Windows 10/11'],
      ['6.3', 'Windows 8.1'],
      ['6.2', 'Windows 8'],
      ['6.1', 'Windows 7'],
    ];

    it.each(ntCases)('maps Windows NT %s to "%s"', (ntVersion, expected) => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent: `Mozilla/5.0 (Windows NT ${ntVersion}; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`,
        },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain(`OS: ${expected}`);
    });

    it('maps an unrecognized Windows NT version to the bare "Windows" fallback', () => {
      // NT 5.1 (XP) is not in the explicit mapping, so it must fall through
      // to the generic `os = 'Windows'` branch (line 97) rather than being
      // dropped or mislabeled.
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Windows NT 5.1; rv:7.0.1) Gecko/20100101 Firefox/7.0.1',
        },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('OS: Windows');
      // Must be the bare fallback, not any of the versioned names.
      expect(decodedUrl).not.toContain('OS: Windows 10/11');
      expect(decodedUrl).not.toContain('OS: Windows 8');
      expect(decodedUrl).not.toContain('OS: Windows 7');
    });

    it('handles a Windows NT token with no parseable version number', () => {
      // "Windows NT" without a trailing version should not crash and should
      // resolve to the bare "Windows" fallback (match is null → version '').
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Windows NT) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('OS: Windows');
    });
  });

  describe('browser name fallback without version (edge cases)', () => {
    // When the browser token is present but the version regex fails to match,
    // the code falls back to the bare browser name (the `: 'Firefox'` etc.
    // ternary branches). These verify each fallback independently.
    it('falls back to bare "Firefox" when no version is parseable', () => {
      Object.defineProperty(global, 'navigator', {
        value: { userAgent: 'Gecko Firefox/ on some device' },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('Browser: Firefox');
      // No numeric version should be appended.
      expect(decodedUrl).not.toMatch(/Browser: Firefox \d/);
    });

    it('falls back to bare "Chrome" when no version is parseable', () => {
      Object.defineProperty(global, 'navigator', {
        value: { userAgent: 'AppleWebKit Chrome/ Safari/537.36' },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('Browser: Chrome');
      expect(decodedUrl).not.toMatch(/Browser: Chrome \d/);
    });

    it('falls back to bare "Edge" when no version is parseable', () => {
      Object.defineProperty(global, 'navigator', {
        value: { userAgent: 'AppleWebKit Chrome/120 Safari/537.36 Edg/' },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('Browser: Edge');
      expect(decodedUrl).not.toMatch(/Browser: Edge \d/);
    });

    it('falls back to bare "Safari" when no Version/ token is present', () => {
      // Safari is detected by the "Safari/" token but versioned by "Version/".
      // A UA with Safari but no Version token exercises the bare fallback.
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15',
        },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('Browser: Safari');
      expect(decodedUrl).not.toMatch(/Browser: Safari \d/);
    });
  });

  describe('mobile/mac OS name fallback without version (edge cases)', () => {
    // The Android/iOS/macOS detectors append a version when the regex matches
    // and fall back to the bare OS name otherwise. These exercise the bare
    // fallback ternary branches (lines 82, 89, 100).
    it('falls back to bare "Android" when no version number is present', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Linux; Android; Pixel) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
        },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('OS: Android');
      expect(decodedUrl).not.toMatch(/OS: Android \d/);
    });

    it('falls back to bare "iOS" when no "OS x_y" version token is present', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (iPhone; CPU like Mac) AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1',
        },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('OS: iOS');
      expect(decodedUrl).not.toMatch(/OS: iOS \d/);
    });

    it('falls back to bare "macOS" when no "Mac OS X x_y" version token is present', () => {
      Object.defineProperty(global, 'navigator', {
        value: {
          userAgent:
            'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        },
        writable: true,
        configurable: true,
      });

      const decodedUrl = decodeURIComponent(
        generateBugReportUrl({ username: 'testuser' })
      );
      expect(decodedUrl).toContain('OS: macOS');
      expect(decodedUrl).not.toMatch(/OS: macOS \d/);
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
