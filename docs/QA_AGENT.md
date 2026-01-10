# QA Agent

## Overview

The QA Agent is a test quality guardian that performs periodic reflection and enhancement of the test suite. Unlike reactive agents that respond to issues, the QA Agent proactively identifies coverage gaps, flaky tests, and missing edge cases to improve overall code quality.

## Problem Statement

Test suites degrade over time without active maintenance:
1. Coverage naturally decreases as new code is added without tests
2. Flaky tests erode confidence in the CI pipeline
3. Edge cases are often overlooked during feature development
4. Integration gaps between frontend and backend go undetected

The QA Agent addresses these by running nightly analysis and improvement sessions.

## Design Principles

### 1. Daily Focus Rotation
Different aspects of test quality are addressed on different days to ensure comprehensive coverage without overwhelming any single session.

### 2. Meaningful Tests Over Coverage Padding
The agent writes tests that validate behavior, not just inflate coverage numbers. Each test should have a clear purpose.

### 3. Progress Visibility
The agent creates a tracking issue for each session, updating checkboxes as work progresses.

### 4. TEST_PLAN.md Synchronization
Every new test must have a corresponding entry in TEST_PLAN.md documenting what it validates.

## Daily Focus Areas

| Day | Focus | Description |
|-----|-------|-------------|
| Monday | Coverage Sprint | Pick lowest-coverage module, increase by 15%+ |
| Tuesday | Flaky Test Hunt | Run tests 5x, identify and fix flaky tests |
| Wednesday | Integration Test Gaps | Find untested API integrations |
| Thursday | E2E Enhancement | Add edge case E2E tests |
| Friday | Test Refactoring | Improve readability, reduce duplication |
| Saturday | Edge Case Analysis | Test error paths and boundary conditions |
| Sunday | Regression Prevention | Add tests for recent bug fixes |

## Responsibilities

### A. Coverage Analysis
```bash
# Backend coverage
cd backend && uv run pytest --cov=app --cov-report=term-missing

# Frontend coverage
cd frontend && npm run test:coverage
```

Identify files with <60% coverage as priority targets.

### B. E2E Test Completeness
Review `frontend/e2e/*.spec.ts` for coverage of:
- [ ] User registration and login
- [ ] Creating new conversations
- [ ] Sending messages and receiving AI responses
- [ ] Pausing/resuming conversations
- [ ] Mobile responsive behavior
- [ ] Error handling (network failures, auth expiry)
- [ ] Admin functionality

### C. Test Sophistication Check
- Are edge cases tested (empty inputs, max lengths, special chars)?
- Are error paths tested (API failures, network issues)?
- Are race conditions considered (concurrent operations)?
- Are boundary conditions tested (0, 1, max values)?

### D. E2E Enhancement Categories

**Edge Cases:**
- Empty form submissions
- Maximum length inputs
- Special characters and unicode
- Rapid repeated actions (double-click, spam)
- Session expiry mid-action
- Network disconnection and reconnection
- Concurrent operations from multiple tabs

**User Journeys:**
1. Happy Path - Normal flow start to finish
2. Error Recovery - What happens when things go wrong
3. State Persistence - Data survives page refresh
4. Accessibility - Keyboard navigation, screen reader compatibility
5. Performance - Page loads within acceptable time

**Mobile-Specific:**
- Touch gestures work correctly
- Viewport-specific layouts render properly
- Virtual keyboard doesn't break layout
- Orientation changes handled gracefully

## Triggers

### Scheduled (Primary)
```yaml
schedule:
  - cron: '0 2 * * *'  # Nightly at 2am UTC
```

### Manual
```yaml
workflow_dispatch:
  inputs:
    focus:
      type: choice
      options:
        - auto-detect
        - coverage-sprint
        - flaky-hunt
        - integration-gaps
        - e2e-enhancement
        - edge-cases
        - test-refactoring
```

## Workflow Structure

```yaml
jobs:
  qa:
    steps:
      - checkout
      - setup python and node
      - install dependencies
      - install Playwright browsers
      - get day of week for focus
      - get current coverage
      - create tracking issue
      - run claude-code-action with QA prompt
      - update issue on failure
```

## Tracking Issue Format

The QA Agent creates an issue for each session:

```markdown
## QA Agent Work Session

**Focus:** coverage-sprint
**Day:** Monday
**Current Coverage:** 72%
**Workflow Run:** [View logs](...)

---

## Progress Checklist

- [ ] 📊 Analyze coverage gaps
- [ ] 📝 Create detailed test plan
- [ ] 🧪 Implement tests
- [ ] ✅ Verify all tests pass 3x
- [ ] 📄 Update TEST_PLAN.md
- [ ] 🚀 Create PR

---

## Coverage Gaps Identified
[Analysis results]

## Test Plan
| File | Current | Target | Tests to Add |
|------|---------|--------|--------------|
| app/api/users.py | 45% | 70% | [tests] |

## Tests Added
- [x] test_user_registration_empty_email
- [x] test_user_registration_invalid_chars
- [ ] test_user_login_rate_limiting

## Final Results
- **Coverage Before:** 72%
- **Coverage After:** 78%
- **PR:** #123
```

## Quality Standards

1. **Run tests 3x minimum** to check for flakiness
2. **Clear descriptions** for every new test
3. **Specific assertions** over generic ones
4. **Test behavior**, not implementation details
5. **Independent tests** - no shared state between tests

## Pre-Commit Requirements

**ALWAYS run formatters before committing:**

```bash
# Backend
cd backend && uv run ruff format . && uv run ruff check . --fix

# Frontend (if changed)
cd frontend && npm run format && npm run lint -- --fix
```

## TEST_PLAN.md Updates

Every new test requires an entry in TEST_PLAN.md:
- Test name and file location
- What the test validates
- Any edge cases covered

## Labels

The QA Agent uses these labels:
- `qa-agent` - All QA Agent tracking issues
- `automation` - Automated by agents
- `factory-meta` - Excluded from other agents (QA issues are meta-work)

## Escalation

Create a GitHub issue and assign to human if:
- Coverage cannot be improved without major refactoring
- Flaky tests require infrastructure changes
- E2E tests need real third-party API access

## Permissions

The QA Agent has standard permissions:
- ✅ Read/write code
- ✅ Create PRs
- ✅ Create/update issues
- ✅ Run tests

## Security Considerations

1. **Don't commit test credentials** - Use environment variables
2. **Clean up test data** - Remove canary users after tests
3. **Don't test against production** - Use test environment only
4. **Careful with E2E tests** - Don't create persistent state

## Success Criteria

1. **Coverage Trend**: Coverage increases by 1%+ per week on average
2. **Flaky Test Rate**: <1% of tests are flaky
3. **E2E Coverage**: All user journeys have E2E tests
4. **Session Completion**: >90% of QA sessions complete successfully
5. **Documentation**: TEST_PLAN.md stays in sync with actual tests
