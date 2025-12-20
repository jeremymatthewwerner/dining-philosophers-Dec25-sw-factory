import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  // Get the pathname of the request
  const { pathname } = request.nextUrl;

  // For static assets with content hashes (JS, CSS, images in _next/static)
  // These files are immutable and can be cached indefinitely
  if (pathname.startsWith('/_next/static/')) {
    response.headers.set(
      'Cache-Control',
      'public, max-age=31536000, immutable'
    );
    return response;
  }

  // For HTML pages and API routes
  // Force revalidation to ensure users get the latest version
  if (
    pathname.endsWith('.html') ||
    pathname === '/' ||
    !pathname.includes('.')
  ) {
    response.headers.set(
      'Cache-Control',
      'no-cache, no-store, must-revalidate, max-age=0'
    );
    response.headers.set('Pragma', 'no-cache');
    response.headers.set('Expires', '0');
    return response;
  }

  // For other static assets (images, fonts, etc in /public)
  // Use a shorter cache time with revalidation
  if (pathname.match(/\.(jpg|jpeg|png|gif|ico|svg|woff|woff2|ttf|eot)$/)) {
    response.headers.set(
      'Cache-Control',
      'public, max-age=3600, must-revalidate'
    );
    return response;
  }

  return response;
}

// Apply middleware to all routes except API routes (handled by Next.js separately)
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/webpack-hmr (webpack hot module reload)
     */
    '/((?!api|_next/webpack-hmr).*)',
  ],
};
