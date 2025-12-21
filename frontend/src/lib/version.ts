/**
 * Application version utilities for cache busting
 */

// Read version from package.json at build time
// This will be embedded in the bundle
export const APP_VERSION =
  process.env.NEXT_PUBLIC_APP_VERSION ||
  process.env.npm_package_version ||
  '0.1.0';

// Generate a build timestamp that changes with each build
export const BUILD_TIMESTAMP = Date.now().toString();

/**
 * Check if a new version is available by comparing with server
 * This is a placeholder for future implementation of version checking
 */
export async function checkForUpdate(): Promise<boolean> {
  try {
    // In the future, this could fetch a version.json from the server
    // and compare it with the current APP_VERSION
    // For now, we rely on the middleware cache headers
    return false;
  } catch (error) {
    console.error('Failed to check for updates:', error);
    return false;
  }
}
