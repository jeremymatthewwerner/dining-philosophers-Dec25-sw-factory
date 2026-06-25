/**
 * E2E Performance-Hygiene Guard
 * ---------------------------------
 * These are fast, browser-less static-analysis tests that LOCK IN the
 * performance work done on the Playwright E2E suite (the Thursday
 * "e2e-performance" QA focus). They read the e2e/*.spec.ts source files and
 * the Playwright config and assert the performance standards documented in
 * `.claude/agents/qa-improver.md` ("Performance Metrics to Track").
 *
 * Why a guard test instead of just optimizing once?
 *   Past e2e-performance sessions kept re-removing the same anti-patterns
 *   because nothing prevented their reintroduction. This suite fails CI the
 *   moment a regression lands, so the gains are permanent.
 *
 * What it enforces:
 *   1. No `page.waitForTimeout(...)` calls   (arbitrary sleeps — top anti-pattern)
 *   2. Every `waitForLoadState('networkidle')` is bounded with a `{ timeout }`
 *      (an unbounded networkidle wait can hang an entire worker)
 *   3. networkidle waits are bounded BELOW a sane cap (networkidle is the
 *      slowest/most-fragile wait type; a 60s networkidle is a known anti-pattern)
 *   4. No per-test `test.setTimeout(...)` above 120s
 *   5. No per-call `{ timeout: N }` above 60s
 *   6. playwright.config keeps CI parallelism: fullyParallel + >=4 CI workers,
 *      a bounded global test timeout, and a bounded expect timeout
 *   7. No spec opts into serial mode (`mode: 'serial'` / `test.describe.serial`),
 *      which overrides fullyParallel and silently serializes a whole file
 *   8. playwright.config retries on CI so a single transient flake doesn't fail
 *      the whole E2E job and force an expensive full re-run
 *   9. playwright.config does not enable always-on tracing (`trace: 'on'`), which
 *      records a trace for EVERY test and materially slows the whole suite
 *
 * Thresholds have headroom over the current suite so legitimate tests are not
 * penalised — they exist to catch runaway values, not to micro-manage.
 */

import { readFileSync, readdirSync } from 'fs';
import { join } from 'path';

const E2E_DIR = join(__dirname, '..', '..', 'e2e');
const PLAYWRIGHT_CONFIG = join(__dirname, '..', '..', 'playwright.config.ts');

// Caps (ms). Generous over current usage; they catch runaway values only.
const MAX_TEST_TIMEOUT_MS = 120_000;
const MAX_CALL_TIMEOUT_MS = 60_000;
const MAX_GLOBAL_TEST_TIMEOUT_MS = 120_000;
// networkidle is the slowest/most-fragile wait type, so it gets a tighter cap
// than generic per-call timeouts. Current suite max is 15s; 30s leaves headroom
// while still catching the 60s networkidle anti-pattern.
const MAX_NETWORKIDLE_TIMEOUT_MS = 30_000;

/** Strip // line comments and block comments so call-site checks ignore prose. */
function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '') // block comments
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1'); // line comments (keep http:// etc.)
}

function listSpecFiles(): string[] {
  return readdirSync(E2E_DIR)
    .filter((f) => f.endsWith('.spec.ts'))
    .map((f) => join(E2E_DIR, f));
}

describe('E2E performance-hygiene guard', () => {
  const specFiles = listSpecFiles();

  it('discovers the e2e spec files to analyze', () => {
    // Sanity check: if this ever returns 0, the path is wrong and the rest of
    // the guard would silently pass without checking anything.
    expect(specFiles.length).toBeGreaterThan(0);
  });

  describe('no arbitrary sleeps (page.waitForTimeout)', () => {
    it.each(listSpecFiles().map((f) => [f]))(
      '%s contains no waitForTimeout() calls',
      (file) => {
        const code = stripComments(readFileSync(file, 'utf-8'));
        const matches = code.match(/\.waitForTimeout\s*\(/g) ?? [];
        expect(matches).toHaveLength(0);
      }
    );
  });

  describe('networkidle waits are bounded with a timeout', () => {
    it.each(listSpecFiles().map((f) => [f]))(
      '%s has no unbounded waitForLoadState(networkidle)',
      (file) => {
        const code = stripComments(readFileSync(file, 'utf-8'));
        // Unbounded form: waitForLoadState('networkidle') with no second arg.
        const unbounded =
          code.match(/waitForLoadState\(\s*(['"`])networkidle\1\s*\)/g) ?? [];
        expect(unbounded).toHaveLength(0);
      }
    );
  });

  describe('networkidle waits stay below a sane cap', () => {
    it.each(listSpecFiles().map((f) => [f]))(
      '%s has no networkidle wait above the cap',
      (file) => {
        const code = stripComments(readFileSync(file, 'utf-8'));
        const offenders: number[] = [];
        // Match waitForLoadState('networkidle', { timeout: N }) and capture N.
        const re =
          /waitForLoadState\(\s*(['"`])networkidle\1\s*,\s*\{[^}]*?timeout:\s*(\d+)/g;
        for (const m of code.matchAll(re)) {
          const value = Number(m[2]);
          if (value > MAX_NETWORKIDLE_TIMEOUT_MS) offenders.push(value);
        }
        expect(offenders).toEqual([]);
      }
    );
  });

  describe('per-test timeouts stay bounded', () => {
    it.each(listSpecFiles().map((f) => [f]))(
      '%s has no test.setTimeout above the cap',
      (file) => {
        const code = stripComments(readFileSync(file, 'utf-8'));
        const offenders: number[] = [];
        for (const m of code.matchAll(/setTimeout\(\s*(\d+)\s*\)/g)) {
          const value = Number(m[1]);
          if (value > MAX_TEST_TIMEOUT_MS) offenders.push(value);
        }
        expect(offenders).toEqual([]);
      }
    );
  });

  describe('per-call timeouts stay bounded', () => {
    it.each(listSpecFiles().map((f) => [f]))(
      '%s has no { timeout: N } above the cap',
      (file) => {
        const code = stripComments(readFileSync(file, 'utf-8'));
        const offenders: number[] = [];
        for (const m of code.matchAll(/timeout:\s*(\d+)/g)) {
          const value = Number(m[1]);
          if (value > MAX_CALL_TIMEOUT_MS) offenders.push(value);
        }
        expect(offenders).toEqual([]);
      }
    );
  });

  describe('parallelism is not silently disabled', () => {
    // fullyParallel runs every test in every file concurrently. The one way a
    // single spec can silently undo that is opting into serial mode, which
    // forces its tests to run one-at-a-time on a single worker. Forbid both the
    // `describe.configure({ mode: 'serial' })` form and the `describe.serial(`
    // / `test.serial(` shorthands.
    it.each(listSpecFiles().map((f) => [f]))(
      '%s does not opt into serial mode',
      (file) => {
        const code = stripComments(readFileSync(file, 'utf-8'));
        const serialMode = code.match(/mode:\s*(['"`])serial\1/g) ?? [];
        const serialShorthand = code.match(/\.serial\s*\(/g) ?? [];
        expect([...serialMode, ...serialShorthand]).toHaveLength(0);
      }
    );
  });

  describe('playwright.config preserves parallelism and bounded timeouts', () => {
    const config = stripComments(readFileSync(PLAYWRIGHT_CONFIG, 'utf-8'));

    it('retries at least once on CI so a single flake does not fail the job', () => {
      // Matches `retries: process.env.CI ? N : ...`
      const m = config.match(/retries:\s*process\.env\.CI\s*\?\s*(\d+)/);
      expect(m).not.toBeNull();
      expect(Number(m?.[1])).toBeGreaterThanOrEqual(1);
    });

    it('enables fullyParallel', () => {
      expect(config).toMatch(/fullyParallel:\s*true/);
    });

    it('uses at least 4 workers in CI', () => {
      // Matches `workers: process.env.CI ? N : ...`
      const m = config.match(/workers:\s*process\.env\.CI\s*\?\s*(\d+)/);
      expect(m).not.toBeNull();
      expect(Number(m?.[1])).toBeGreaterThanOrEqual(4);
    });

    it('bounds the global test timeout', () => {
      const m = config.match(/^\s*timeout:\s*(\d+)/m);
      expect(m).not.toBeNull();
      expect(Number(m?.[1])).toBeLessThanOrEqual(MAX_GLOBAL_TEST_TIMEOUT_MS);
    });

    it('bounds the expect() assertion timeout', () => {
      const m = config.match(/expect:\s*\{\s*timeout:\s*(\d+)/);
      expect(m).not.toBeNull();
      expect(Number(m?.[1])).toBeGreaterThan(0);
      expect(Number(m?.[1])).toBeLessThanOrEqual(MAX_CALL_TIMEOUT_MS);
    });

    it('does not enable always-on tracing', () => {
      // `trace: 'on'` records a Playwright trace for EVERY test, which adds
      // significant per-test overhead across the whole suite. Conditional modes
      // like 'on-first-retry' or 'retain-on-failure' only pay that cost when a
      // test actually fails, so they are the performant choice.
      const m = config.match(/trace:\s*(['"`])([^'"`]+)\1/);
      expect(m).not.toBeNull();
      expect(m?.[2]).not.toBe('on');
    });
  });
});
