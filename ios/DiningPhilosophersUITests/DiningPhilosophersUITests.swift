// DiningPhilosophersUITests.swift
// UI tests for the DiningPhilosophers app
//
// Created by iOS Native Agent

import XCTest

/// Main UI test class for DiningPhilosophers app
final class DiningPhilosophersUITests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--uitesting"]
    }

    override func tearDownWithError() throws {
        app = nil
    }

    // MARK: - Login Flow Tests

    func testLoginScreenAppearsOnLaunch() throws {
        app.launch()

        // Verify login screen elements
        XCTAssertTrue(app.staticTexts["Dining Philosophers"].exists)
        XCTAssertTrue(app.textFields["Username"].exists)
        XCTAssertTrue(app.secureTextFields["Password"].exists)
        XCTAssertTrue(app.buttons["Sign In"].exists)
    }

    func testCanToggleBetweenLoginAndRegister() throws {
        app.launch()

        // Should start on login
        XCTAssertTrue(app.buttons["Sign In"].exists)

        // Tap to switch to register
        let toggleButton = app.buttons["Don't have an account? Create one"]
        XCTAssertTrue(toggleButton.waitForExistence(timeout: 5))
        toggleButton.tap()

        // Should now show register
        XCTAssertTrue(app.buttons["Create Account"].waitForExistence(timeout: 2))
        XCTAssertTrue(app.textFields["Display Name (optional)"].exists)

        // Tap to switch back to login
        let switchBackButton = app.buttons["Already have an account? Sign In"]
        XCTAssertTrue(switchBackButton.exists)
        switchBackButton.tap()

        // Should be back on login
        XCTAssertTrue(app.buttons["Sign In"].waitForExistence(timeout: 2))
    }

    func testSignInButtonDisabledWithEmptyFields() throws {
        app.launch()

        let signInButton = app.buttons["Sign In"]
        XCTAssertTrue(signInButton.exists)

        // Button should be disabled initially
        XCTAssertFalse(signInButton.isEnabled)

        // Enter only username
        let usernameField = app.textFields["Username"]
        usernameField.tap()
        usernameField.typeText("testuser")

        // Still disabled (no password)
        XCTAssertFalse(signInButton.isEnabled)

        // Enter short password (less than 6 chars)
        let passwordField = app.secureTextFields["Password"]
        passwordField.tap()
        passwordField.typeText("12345")

        // Still disabled (password too short)
        XCTAssertFalse(signInButton.isEnabled)

        // Complete password
        passwordField.typeText("6")

        // Now should be enabled
        XCTAssertTrue(signInButton.isEnabled)
    }

    // MARK: - Accessibility Tests

    func testLoginScreenAccessibility() throws {
        app.launch()

        // Verify accessibility labels exist
        XCTAssertTrue(app.textFields["Username"].exists)
        XCTAssertTrue(app.secureTextFields["Password"].exists)

        // App icon should have accessibility
        let appIcon = app.images.firstMatch
        XCTAssertNotNil(appIcon)
    }

    // MARK: - Navigation Tests

    func testAppNameDisplayedCorrectly() throws {
        app.launch()

        // Check the app name appears
        let appName = app.staticTexts["Dining Philosophers"]
        XCTAssertTrue(appName.waitForExistence(timeout: 5))

        // Check tagline
        let tagline = app.staticTexts["Chat with history's greatest thinkers"]
        XCTAssertTrue(tagline.exists)
    }
}
