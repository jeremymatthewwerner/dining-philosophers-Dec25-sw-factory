// DiningPhilosophersUITests.swift
// UI tests for the Dining Philosophers iOS app
//
// Created by iOS Native Agent

import XCTest

final class DiningPhilosophersUITests: XCTestCase {

    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launch()
    }

    override func tearDownWithError() throws {
        app = nil
    }

    // MARK: - Login Screen Tests

    func testLoginScreenElements() throws {
        // Verify login screen elements are present
        XCTAssertTrue(app.staticTexts["Dining Philosophers"].exists)
        XCTAssertTrue(app.textFields["Username"].exists)
        XCTAssertTrue(app.secureTextFields["Password"].exists)
        XCTAssertTrue(app.buttons["Sign In"].exists)
    }

    func testToggleToRegistration() throws {
        // Find and tap the toggle button
        let toggleButton = app.buttons["Don't have an account? Create one"]
        XCTAssertTrue(toggleButton.exists)

        toggleButton.tap()

        // Verify registration elements appear
        XCTAssertTrue(app.navigationBars["Create Account"].exists)
        XCTAssertTrue(app.textFields["Display Name (optional)"].exists)
        XCTAssertTrue(app.buttons["Create Account"].exists)
    }

    func testToggleBackToLogin() throws {
        // Toggle to registration
        app.buttons["Don't have an account? Create one"].tap()

        // Toggle back to login
        let toggleBackButton = app.buttons["Already have an account? Sign In"]
        XCTAssertTrue(toggleBackButton.exists)

        toggleBackButton.tap()

        // Verify we're back on login
        XCTAssertTrue(app.navigationBars["Sign In"].exists)
    }

    func testSignInButtonDisabledWithEmptyFields() throws {
        let signInButton = app.buttons["Sign In"]

        // Button should be disabled with empty fields
        XCTAssertFalse(signInButton.isEnabled)

        // Enter username only
        let usernameField = app.textFields["Username"]
        usernameField.tap()
        usernameField.typeText("testuser")

        // Still disabled - no password
        XCTAssertFalse(signInButton.isEnabled)

        // Enter short password
        let passwordField = app.secureTextFields["Password"]
        passwordField.tap()
        passwordField.typeText("12345")

        // Still disabled - password too short (< 6 chars)
        XCTAssertFalse(signInButton.isEnabled)

        // Enter valid password
        passwordField.typeText("6")  // Now "123456"

        // Button should be enabled
        XCTAssertTrue(signInButton.isEnabled)
    }

    // MARK: - Accessibility Tests

    func testLoginScreenAccessibility() throws {
        // Verify all interactive elements have accessibility labels
        XCTAssertTrue(app.textFields["Username"].isHittable)
        XCTAssertTrue(app.secureTextFields["Password"].isHittable)
        XCTAssertTrue(app.buttons["Sign In"].isHittable)
    }
}
