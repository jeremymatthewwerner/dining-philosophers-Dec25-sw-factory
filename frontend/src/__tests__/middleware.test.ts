/**
 * @jest-environment node
 *
 * Unit tests for the cache-control middleware (`src/middleware.ts`).
 *
 * Next.js middleware runs in the Edge Runtime, which exposes the web
 * `Request`/`Response`/`Headers` globals rather than jsdom's browser globals.
 * The default jsdom test environment does not define `Request`, so importing
 * `next/server` there throws `ReferenceError: Request is not defined`. This
 * file therefore opts into the Node test environment via the `@jest-environment
 * node` docblock above (Node 18+ provides the web fetch globals natively).
 *
 * Previously this suite was a placeholder that only asserted string constants
 * and never invoked `middleware()`, leaving the module at 0% coverage. These
 * tests exercise every branch of the cache-control logic directly.
 */
import { NextRequest } from 'next/server';

import { config, middleware } from '@/middleware';

/** Build a NextRequest for the given absolute path on a dummy origin. */
function requestFor(path: string): NextRequest {
  return new NextRequest(new URL(`http://localhost${path}`));
}

describe('cache-control middleware', () => {
  describe('hashed static assets under /_next/static/', () => {
    it('caches JS chunks immutably for a year', () => {
      const res = middleware(requestFor('/_next/static/chunks/main-abc123.js'));
      expect(res.headers.get('Cache-Control')).toBe(
        'public, max-age=31536000, immutable'
      );
    });

    it('caches CSS the same way', () => {
      const res = middleware(requestFor('/_next/static/css/app-deadbeef.css'));
      expect(res.headers.get('Cache-Control')).toBe(
        'public, max-age=31536000, immutable'
      );
    });

    it('does not set the no-cache HTML headers for static assets', () => {
      const res = middleware(requestFor('/_next/static/chunks/x.js'));
      expect(res.headers.get('Pragma')).toBeNull();
      expect(res.headers.get('Expires')).toBeNull();
    });

    it('prefers the immutable static branch over the image branch for a static image', () => {
      // /_next/static/ is checked first, so even a .png under it must be
      // immutable rather than the shorter must-revalidate image policy.
      const res = middleware(requestFor('/_next/static/media/logo.4f2a.png'));
      expect(res.headers.get('Cache-Control')).toBe(
        'public, max-age=31536000, immutable'
      );
    });
  });

  describe('HTML pages, the root path, and extensionless routes', () => {
    const noCache = 'no-cache, no-store, must-revalidate, max-age=0';

    it('forces revalidation on the root path', () => {
      const res = middleware(requestFor('/'));
      expect(res.headers.get('Cache-Control')).toBe(noCache);
      expect(res.headers.get('Pragma')).toBe('no-cache');
      expect(res.headers.get('Expires')).toBe('0');
    });

    it('forces revalidation on explicit .html pages', () => {
      const res = middleware(requestFor('/about.html'));
      expect(res.headers.get('Cache-Control')).toBe(noCache);
      expect(res.headers.get('Pragma')).toBe('no-cache');
    });

    it('forces revalidation on extensionless app routes', () => {
      // e.g. /login, /settings — no "." in the pathname
      const res = middleware(requestFor('/login'));
      expect(res.headers.get('Cache-Control')).toBe(noCache);
      expect(res.headers.get('Expires')).toBe('0');
    });

    it('treats nested extensionless routes as pages too', () => {
      const res = middleware(requestFor('/admin/users'));
      expect(res.headers.get('Cache-Control')).toBe(noCache);
    });
  });

  describe('public static assets (images and fonts)', () => {
    const mustRevalidate = 'public, max-age=3600, must-revalidate';

    it.each([
      '/photo.jpg',
      '/photo.jpeg',
      '/logo.png',
      '/anim.gif',
      '/favicon.ico',
      '/icon.svg',
      '/font.woff',
      '/font.woff2',
      '/font.ttf',
      '/legacy.eot',
    ])('uses a short revalidating cache for %s', (path) => {
      const res = middleware(requestFor(path));
      expect(res.headers.get('Cache-Control')).toBe(mustRevalidate);
      // Image/font branch must not set the HTML no-cache headers.
      expect(res.headers.get('Pragma')).toBeNull();
    });

    it('matches asset extensions case-sensitively (regex has no /i flag)', () => {
      // The extension regex is anchored and case-sensitive, so an uppercase
      // extension does NOT hit the image branch and falls through with no
      // Cache-Control header. This pins the current behavior.
      const res = middleware(requestFor('/Banner.PNG'));
      expect(res.headers.get('Cache-Control')).toBeNull();
    });
  });

  describe('fallthrough for other extensioned paths', () => {
    it.each(['/data.json', '/notes.txt', '/archive.zip', '/feed.xml'])(
      'leaves %s with no Cache-Control header (pass-through response)',
      (path) => {
        const res = middleware(requestFor(path));
        expect(res.headers.get('Cache-Control')).toBeNull();
        expect(res.headers.get('Pragma')).toBeNull();
        expect(res.headers.get('Expires')).toBeNull();
      }
    );
  });

  describe('exported matcher config', () => {
    it('exposes a matcher that excludes api and webpack-hmr routes', () => {
      expect(config).toBeDefined();
      expect(config.matcher).toEqual(['/((?!api|_next/webpack-hmr).*)']);
    });
  });
});
