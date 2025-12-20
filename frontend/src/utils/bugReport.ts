/**
 * Utility functions for generating bug report URLs
 */

export interface BugReportParams {
  username?: string;
  displayName?: string | null;
}

/**
 * Generates a GitHub issue URL pre-populated with user information and browser details
 */
export function generateBugReportUrl(params: BugReportParams): string {
  const { username, displayName } = params;

  // Get user agent information (browser/device)
  const userAgent =
    typeof navigator !== 'undefined' ? navigator.userAgent : 'Unknown';

  // Parse user agent to extract readable browser/OS info
  const browserInfo = getBrowserInfo(userAgent);

  // Build the user info section
  const nameToShow = displayName || username || 'Unknown User';
  const userInfoSection = `**Filed from thinkers-chat app by ${nameToShow}**
- Username: ${username || 'Not available'}
${displayName ? `- Display Name: ${displayName}` : ''}
- Browser: ${browserInfo.browser}
- OS: ${browserInfo.os}
- User Agent: \`${userAgent}\``;

  // Build the issue body with user info
  const body = `## Description
Please describe the issue:

## Steps to Reproduce
1.
2.

## Expected Behavior


## Actual Behavior


## Browser/Device
${userInfoSection}`;

  // URL encode the parameters
  const title = encodeURIComponent('');
  const encodedBody = encodeURIComponent(body);
  const labels = encodeURIComponent('P3');

  return `https://github.com/jeremymatthewwerner/thinkers-chat/issues/new?title=${title}&body=${encodedBody}&labels=${labels}`;
}

/**
 * Parses user agent string to extract browser and OS information
 */
function getBrowserInfo(userAgent: string): { browser: string; os: string } {
  let browser = 'Unknown Browser';
  let os = 'Unknown OS';

  // Detect browser
  if (userAgent.includes('Firefox/')) {
    const match = userAgent.match(/Firefox\/(\d+\.\d+)/);
    browser = match ? `Firefox ${match[1]}` : 'Firefox';
  } else if (userAgent.includes('Edg/')) {
    const match = userAgent.match(/Edg\/(\d+\.\d+)/);
    browser = match ? `Edge ${match[1]}` : 'Edge';
  } else if (userAgent.includes('Chrome/')) {
    const match = userAgent.match(/Chrome\/(\d+\.\d+)/);
    browser = match ? `Chrome ${match[1]}` : 'Chrome';
  } else if (userAgent.includes('Safari/')) {
    const match = userAgent.match(/Version\/(\d+\.\d+)/);
    browser = match ? `Safari ${match[1]}` : 'Safari';
  }

  // Detect OS (check mobile OSes first as they often contain desktop OS keywords)
  if (userAgent.includes('Android')) {
    const match = userAgent.match(/Android (\d+(\.\d+)?)/);
    os = match ? `Android ${match[1]}` : 'Android';
  } else if (
    userAgent.includes('iOS') ||
    userAgent.includes('iPhone') ||
    userAgent.includes('iPad')
  ) {
    const match = userAgent.match(/OS (\d+_\d+(_\d+)?)/);
    os = match ? `iOS ${match[1].replace(/_/g, '.')}` : 'iOS';
  } else if (userAgent.includes('Windows NT')) {
    const match = userAgent.match(/Windows NT (\d+\.\d+)/);
    const version = match ? match[1] : '';
    if (version === '10.0') os = 'Windows 10/11';
    else if (version === '6.3') os = 'Windows 8.1';
    else if (version === '6.2') os = 'Windows 8';
    else if (version === '6.1') os = 'Windows 7';
    else os = 'Windows';
  } else if (userAgent.includes('Mac OS X')) {
    const match = userAgent.match(/Mac OS X (\d+[._]\d+([._]\d+)?)/);
    os = match ? `macOS ${match[1].replace(/_/g, '.')}` : 'macOS';
  } else if (userAgent.includes('Linux')) {
    os = 'Linux';
  }

  return { browser, os };
}
