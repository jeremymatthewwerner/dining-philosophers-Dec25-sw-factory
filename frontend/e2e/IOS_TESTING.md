# iOS Safari E2E Testing Guide

This document explains how to run and maintain iOS Safari-specific E2E tests for the Dining Philosophers application.

## Overview

iOS Safari has unique rendering behaviors and quirks that require specific testing. Our test suite includes:
- **WebKit-based tests** - Using Playwright's WebKit engine (simulates Safari)
- **Real device testing** - Options for testing on actual iOS devices
- **Multiple device profiles** - iPhone SE, iPhone 13, iPhone 14 Pro, iPad Pro

## Quick Start

### Run all iOS tests
```bash
cd frontend
npx playwright test mobile-ios
```

### Run tests on specific iOS device
```bash
# iPhone 13
npx playwright test mobile-ios --project=ios-safari-iphone-13

# iPhone SE (smallest viewport)
npx playwright test mobile-ios --project=ios-safari-iphone-se

# iPhone 14 Pro (Dynamic Island)
npx playwright test mobile-ios --project=ios-safari-iphone-14-pro

# iPad Pro (tablet layout)
npx playwright test mobile-ios --project=ios-safari-ipad-pro
```

### Run specific test suite
```bash
# Header visibility tests
npx playwright test mobile-ios -g "Header Visibility"

# Sidebar toggle tests
npx playwright test mobile-ios -g "Sidebar Toggle"

# Orientation change tests
npx playwright test mobile-ios -g "Orientation Changes"
```

## Test Coverage

### iOS-Specific Features Tested

1. **Header Visibility** (mobile-ios.spec.ts:18-105)
   - Header visible after chat selection
   - Sticky positioning during scroll
   - Dynamic Island compatibility (iPhone 14 Pro)
   - No WebKit transform interference

2. **Sidebar Toggle** (mobile-ios.spec.ts:107-168)
   - Open/close functionality
   - Reopen after closing
   - Animation handling

3. **Sticky Positioning** (mobile-ios.spec.ts:170-233)
   - Maintains position during scroll
   - Works with iOS safe areas
   - CSS sticky compatibility

4. **Orientation Changes** (mobile-ios.spec.ts:235-308)
   - Portrait ↔ Landscape transitions
   - Multiple orientation changes
   - Layout reflow handling

5. **iPad Specific** (mobile-ios.spec.ts:310-349)
   - iPad Pro layout
   - Split view simulation

6. **Touch Interactions** (mobile-ios.spec.ts:351-401)
   - 44x44pt minimum touch targets
   - Tap event handling

7. **Viewport & Safe Areas** (mobile-ios.spec.ts:403-443)
   - Viewport meta tag configuration
   - Safe area inset support
   - Notch/Dynamic Island handling

8. **Regression Tests** (mobile-ios.spec.ts:445-503)
   - Issue #215: WebKit transform bug
   - Issue #217: Sticky positioning fix

## Device Profiles

Our test suite covers these iOS device configurations:

| Device | Viewport | Notes |
|--------|----------|-------|
| iPhone SE | 375x667 | Smallest modern iPhone, critical for minimum size testing |
| iPhone 13 | 390x844 | Standard modern iPhone |
| iPhone 14 Pro | 393x852 | Dynamic Island, latest features |
| iPad Pro | 1024x1366 | Tablet layout, larger viewport |

## Testing Approaches

### 1. WebKit Engine (Default)

**What it is:** Playwright uses WebKit (Safari's rendering engine) to simulate iOS Safari behavior.

**Pros:**
- Fast and automated
- No special hardware required
- Runs in CI/CD pipeline
- Good approximation of Safari behavior

**Cons:**
- Not 100% identical to real iOS Safari
- May miss device-specific quirks
- No touch hardware simulation

**How to use:**
```bash
npx playwright test mobile-ios
```

### 2. Real iOS Device (Manual)

**What it is:** Test the app on a physical iPhone or iPad.

**Pros:**
- 100% accurate iOS Safari behavior
- Real touch interactions
- Actual device performance

**Cons:**
- Requires physical device
- Slow and manual
- Hard to automate

**How to use:**
1. Deploy app to accessible URL (staging/localhost tunnel)
2. Open URL in Safari on iOS device
3. Manually execute test scenarios

**Manual test checklist:**
- [ ] Header visible after selecting conversation
- [ ] Header stays visible during scroll
- [ ] Sidebar opens and closes
- [ ] Rotate device - layout adapts
- [ ] All buttons are tappable
- [ ] No content hidden behind notch

### 3. BrowserStack / Sauce Labs (Paid)

**What it is:** Cloud-based real device testing services.

**Pros:**
- Access to many real iOS devices
- Automated testing possible
- Screenshots and video recording
- Multiple iOS versions

**Cons:**
- Requires paid subscription
- Slower than local testing
- Network latency

**Setup (BrowserStack example):**
```bash
# Install BrowserStack local
npm install -g browserstack-local

# Update playwright.config.ts
export default defineConfig({
  use: {
    connectOptions: {
      wsEndpoint: 'wss://cdp.browserstack.com/playwright?caps=...'
    }
  }
});

# Run tests
BROWSERSTACK_USERNAME=user BROWSERSTACK_ACCESS_KEY=key npx playwright test
```

### 4. iOS Simulator (macOS Only)

**What it is:** Use Xcode's iOS Simulator for testing.

**Pros:**
- More accurate than WebKit alone
- Free (if you have macOS)
- Faster than real device

**Cons:**
- Requires macOS and Xcode
- Still not 100% like real device
- Setup complexity

**Setup:**
```bash
# Install Xcode from Mac App Store
# Open Xcode > Settings > Platforms > Install iOS simulator

# Install playwright webkit
npx playwright install webkit

# Run against simulator (requires special setup)
# See: https://playwright.dev/docs/test-mobile
```

## Known iOS Safari Issues

### Issue #215: Header Visibility Bug
- **Problem:** Header was invisible on iOS due to WebKit transform
- **Fix:** Removed problematic transform styles
- **Test:** `mobile-ios.spec.ts:476` - Verifies no transform on header

### Issue #217: Sticky Positioning
- **Problem:** Sticky positioning wasn't working correctly on iOS
- **Fix:** Added iOS-specific CSS fallbacks
- **Test:** `mobile-ios.spec.ts:489` - Verifies sticky position works

### Issue #218: iOS CSS Fallbacks (Pending)
- **Problem:** Need `-webkit-sticky` fallback for older iOS
- **Status:** In progress
- **Test:** Covered in sticky positioning tests

### Issue #219: Sidebar Toggle (Pending)
- **Problem:** Sidebar doesn't toggle correctly on iOS
- **Status:** In progress
- **Test:** `mobile-ios.spec.ts:107-168` - Will validate fix

## Writing New iOS Tests

### Test Template
```typescript
test('describe your test', async ({ page }) => {
  await setupAuthenticatedUser(page);
  await createConversationViaUI(page, 'Test topic', 'Thinker');

  // Your test logic here

  // Always verify header visibility
  await expect(page.getByTestId('chat-area')).toBeVisible();
  const header = page.getByTestId('chat-area').locator('div').first();
  await expect(header).toBeVisible();
});
```

### Best Practices

1. **Always wait for animations**
   ```typescript
   await page.waitForTimeout(300); // iOS animations can be slow
   ```

2. **Use tap() instead of click() for touch events**
   ```typescript
   await button.tap(); // Better for mobile testing
   ```

3. **Check bounding boxes for visibility**
   ```typescript
   const box = await element.boundingBox();
   expect(box).not.toBeNull();
   expect(box.y).toBeGreaterThanOrEqual(0); // Not hidden off-screen
   ```

4. **Test multiple device sizes**
   - Always test on smallest (iPhone SE) and largest (iPad Pro)
   - Include tests for both portrait and landscape

5. **Verify safe areas**
   ```typescript
   // Check for notch/Dynamic Island compatibility
   const headerBox = await header.boundingBox();
   expect(headerBox.y).toBeGreaterThanOrEqual(0); // Not behind notch
   ```

6. **Test sticky positioning explicitly**
   ```typescript
   const position = await element.evaluate((el) => {
     return window.getComputedStyle(el).position;
   });
   expect(position).toBe('sticky');
   ```

## Debugging iOS Tests

### View test results
```bash
npx playwright show-report
```

### Run in headed mode (see browser)
```bash
npx playwright test mobile-ios --headed --project=ios-safari-iphone-13
```

### Debug specific test
```bash
npx playwright test mobile-ios -g "header visible" --debug
```

### Generate screenshots
```typescript
await page.screenshot({ path: 'ios-debug.png', fullPage: true });
```

### Enable trace viewer
```bash
npx playwright test mobile-ios --trace on
npx playwright show-trace trace.zip
```

## CI/CD Integration

iOS tests run automatically in CI/CD pipeline:
- All iOS device configurations are tested
- Screenshots captured on failure
- Tests must pass before merge

### Skip iOS tests locally (faster iteration)
```bash
npx playwright test --ignore-snapshots --project=chromium
```

### Run only iOS tests in CI
```bash
npx playwright test mobile-ios --project=ios-safari-*
```

## Performance Considerations

- iOS tests can be slower due to:
  - WebKit startup time
  - Animation delays
  - Multiple device configurations

- Optimize by:
  - Running chromium tests first (faster feedback)
  - Using `--shard` to parallelize iOS tests
  - Reducing test timeouts where safe

## Further Resources

- [Playwright Mobile Testing](https://playwright.dev/docs/emulation)
- [iOS Safari WebKit Blog](https://webkit.org/blog/)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/ios)
- [BrowserStack Playwright Integration](https://www.browserstack.com/docs/automate/playwright)
- [Sauce Labs Playwright Guide](https://docs.saucelabs.com/web-apps/automated-testing/playwright/)

## Support

For issues with iOS testing:
1. Check existing GitHub issues (#212, #215, #217, #218, #219)
2. Review recent CI/CD failures
3. Test on real iOS device to confirm behavior
4. File new issue with device details and screenshots
