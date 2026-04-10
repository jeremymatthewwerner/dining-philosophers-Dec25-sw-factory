/**
 * Tests for the hooks barrel export (src/hooks/index.ts).
 *
 * Verifies that all hooks are exported correctly through the barrel file.
 */

import * as HooksBarrel from '@/hooks';

describe('Hooks barrel exports', () => {
  it('exports useWebSocket hook', () => {
    expect(HooksBarrel.useWebSocket).toBeDefined();
    expect(typeof HooksBarrel.useWebSocket).toBe('function');
  });
});
