/**
 * Tests for version.ts utility module.
 *
 * Covers:
 * - APP_VERSION falls back correctly through env vars
 * - BUILD_TIMESTAMP is a numeric string
 * - checkForUpdate always returns false (placeholder implementation)
 */

describe('version utilities', () => {
  describe('APP_VERSION', () => {
    it('exports APP_VERSION as a string', async () => {
      const { APP_VERSION } = await import('@/lib/version');
      expect(typeof APP_VERSION).toBe('string');
      expect(APP_VERSION.length).toBeGreaterThan(0);
    });

    it('APP_VERSION defaults to 0.1.0 when env vars are not set', async () => {
      jest.resetModules();

      const originalNextPublic = process.env.NEXT_PUBLIC_APP_VERSION;
      const originalNpm = process.env.npm_package_version;

      delete process.env.NEXT_PUBLIC_APP_VERSION;
      delete process.env.npm_package_version;

      const { APP_VERSION } = await import('@/lib/version');
      expect(APP_VERSION).toBe('0.1.0');

      // Restore
      if (originalNextPublic !== undefined) {
        process.env.NEXT_PUBLIC_APP_VERSION = originalNextPublic;
      }
      if (originalNpm !== undefined) {
        process.env.npm_package_version = originalNpm;
      }
      jest.resetModules();
    });

    it('APP_VERSION uses NEXT_PUBLIC_APP_VERSION when set', async () => {
      jest.resetModules();

      const originalNextPublic = process.env.NEXT_PUBLIC_APP_VERSION;
      process.env.NEXT_PUBLIC_APP_VERSION = '2.0.0';

      const { APP_VERSION } = await import('@/lib/version');
      expect(APP_VERSION).toBe('2.0.0');

      // Restore
      if (originalNextPublic !== undefined) {
        process.env.NEXT_PUBLIC_APP_VERSION = originalNextPublic;
      } else {
        delete process.env.NEXT_PUBLIC_APP_VERSION;
      }
      jest.resetModules();
    });
  });

  describe('BUILD_TIMESTAMP', () => {
    it('exports BUILD_TIMESTAMP as a numeric string', async () => {
      const { BUILD_TIMESTAMP } = await import('@/lib/version');
      expect(typeof BUILD_TIMESTAMP).toBe('string');
      expect(Number(BUILD_TIMESTAMP)).not.toBeNaN();
      // Timestamp should be reasonable (after year 2020)
      expect(Number(BUILD_TIMESTAMP)).toBeGreaterThan(1577836800000);
    });
  });

  describe('checkForUpdate', () => {
    it('returns false (placeholder implementation)', async () => {
      const { checkForUpdate } = await import('@/lib/version');
      const result = await checkForUpdate();
      expect(result).toBe(false);
    });

    it('returns false multiple times', async () => {
      const { checkForUpdate } = await import('@/lib/version');
      const results = await Promise.all([
        checkForUpdate(),
        checkForUpdate(),
        checkForUpdate(),
      ]);
      expect(results).toEqual([false, false, false]);
    });
  });
});
