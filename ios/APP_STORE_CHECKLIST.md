# App Store Preparation Checklist

This document tracks the remaining tasks for App Store submission.

## Completed (Automated)

- [x] **App Icon Asset Catalog** - 1024x1024 placeholder icon created at `DiningPhilosophers/Resources/Assets.xcassets/AppIcon.appiconset/`
- [x] **Launch Screen Configuration** - Configured via Info.plist with LaunchIcon image
- [x] **Bundle Configuration** - Bundle ID: `ai.diningphilosophers.app`, Category: Social Networking
- [x] **Encryption Declaration** - `ITSAppUsesNonExemptEncryption` set to `false`

## Required Human Actions

### 1. Apple Developer Program (Required)

- [ ] **Enroll in Apple Developer Program** - $99/year at [developer.apple.com](https://developer.apple.com/programs/enroll/)
- [ ] **Create App ID** in Apple Developer portal matching bundle ID: `ai.diningphilosophers.app`
- [ ] **Create Signing Certificates** (Development + Distribution)
- [ ] **Create Provisioning Profiles** (Development + App Store)

### 2. App Icon (Design Required)

The current app icon is a placeholder showing "DP" in a thought bubble. For App Store submission:

- [ ] **Design final app icon** - Should be distinctive, recognizable at small sizes
- [ ] **Replace placeholder** at `ios/DiningPhilosophers/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png`
- [ ] Required: 1024x1024px PNG without transparency

**Design Guidelines:**
- No alpha channel (transparency)
- No rounded corners (iOS adds them automatically)
- Avoid small text that's unreadable at 29px
- Consider how it looks on both light and dark home screens

### 3. App Store Connect Setup

- [ ] **Create new app** in App Store Connect
- [ ] **Configure pricing** (Free, paid, or freemium)
- [ ] **Select primary category** (suggested: Social Networking)
- [ ] **Configure age rating** (answer questionnaire)

### 4. App Store Screenshots

Required sizes:
- [ ] **6.7" Display** (iPhone 15 Pro Max) - 1290 x 2796 pixels
- [ ] **6.5" Display** (iPhone 14 Plus) - 1284 x 2778 pixels
- [ ] **5.5" Display** (iPhone 8 Plus) - 1242 x 2208 pixels

**Screenshot Tips:**
- Use Xcode Simulator to capture screenshots
- Consider using [fastlane snapshot](https://docs.fastlane.tools/actions/snapshot/) for automation
- Show key features: conversation list, chat view, thinker browser
- Add marketing text overlays if desired

### 5. App Store Metadata

- [ ] **App Name** (30 characters max): "Dining Philosophers"
- [ ] **Subtitle** (30 characters max): Suggested: "Chat with History's Greatest Minds"
- [ ] **Description** (4000 characters max): Write compelling description
- [ ] **Keywords** (100 characters): Suggested: "philosophy,chat,AI,history,Socrates,Aristotle,debate,conversation"
- [ ] **Support URL**: Link to support page
- [ ] **Marketing URL** (optional): Link to marketing page

### 6. Legal Documents

- [ ] **Privacy Policy URL** - Required, must be hosted publicly
  - What data is collected
  - How data is used
  - Third-party services (API, analytics)
  - User rights and data deletion

- [ ] **Terms of Service URL** (recommended)
  - Acceptable use policy
  - Service limitations
  - Liability disclaimers

### 7. TestFlight Beta Testing

- [ ] **Upload build** via Xcode or `fastlane pilot`
- [ ] **Add internal testers** (up to 100)
- [ ] **Configure external testing** (optional, requires review)
- [ ] **Test all features** on real devices
- [ ] **Fix any issues** found during testing

### 8. Final Submission

- [ ] **Review App Store Guidelines** - [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [ ] **Submit for review**
- [ ] **Respond to any review feedback**
- [ ] **Release app** (manual or automatic)

## Fastlane Setup (Recommended)

For automated deployment, consider setting up [fastlane](https://fastlane.tools/):

```bash
cd ios
fastlane init
```

Create `ios/fastlane/Fastfile`:

```ruby
default_platform(:ios)

platform :ios do
  desc "Build and upload to TestFlight"
  lane :beta do
    increment_build_number
    build_app(scheme: "DiningPhilosophers")
    upload_to_testflight
  end

  desc "Deploy to App Store"
  lane :release do
    build_app(scheme: "DiningPhilosophers")
    upload_to_app_store
  end
end
```

## Timeline Estimate

| Phase | Tasks |
|-------|-------|
| Initial Setup | Apple Developer enrollment, certificates, profiles |
| Design | Final app icon, screenshots |
| Metadata | App Store listing, legal documents |
| Testing | TestFlight internal + external testing |
| Submission | Review process (typically 24-48 hours) |

## Resources

- [App Store Connect](https://appstoreconnect.apple.com/)
- [Apple Developer Portal](https://developer.apple.com/)
- [Human Interface Guidelines - App Icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)
- [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [Fastlane Documentation](https://docs.fastlane.tools/)
