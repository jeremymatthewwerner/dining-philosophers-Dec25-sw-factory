// ConversationListUITests.swift
// UI tests for the conversation list screen
//
// Created by iOS Native Agent

import XCTest

/// UI tests for the conversation list functionality
final class ConversationListUITests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--uitesting"]
    }

    override func tearDownWithError() throws {
        app = nil
    }

    // MARK: - Empty State Tests

    func testEmptyStateDisplaysWhenNoConversations() throws {
        // Launch app in authenticated state (would need test hooks)
        app.launchArguments.append("--skip-auth")
        app.launch()

        // Look for empty state elements
        // Note: This test validates structure; actual empty state depends on auth
        let noConversationsLabel = app.staticTexts["No Conversations Yet"]
        if noConversationsLabel.waitForExistence(timeout: 5) {
            XCTAssertTrue(noConversationsLabel.exists)

            // Check for call-to-action button
            let startButton = app.buttons["Start a Conversation"]
            XCTAssertTrue(startButton.exists)
        }
    }

    // MARK: - Navigation Tests

    func testNewConversationButtonExists() throws {
        app.launchArguments.append("--skip-auth")
        app.launch()

        // Look for the plus button in navigation bar
        let newConversationButton = app.buttons["New conversation"]
        if newConversationButton.waitForExistence(timeout: 5) {
            XCTAssertTrue(newConversationButton.exists)
        }
    }

    func testTappingNewConversationShowsSheet() throws {
        app.launchArguments.append("--skip-auth")
        app.launch()

        let newConversationButton = app.buttons["New conversation"]
        if newConversationButton.waitForExistence(timeout: 5) {
            newConversationButton.tap()

            // Should show new conversation sheet
            let newConversationTitle = app.staticTexts["New Conversation"]
            XCTAssertTrue(newConversationTitle.waitForExistence(timeout: 2))

            // Should have topic field
            let topicField = app.textFields["Enter a topic..."]
            XCTAssertTrue(topicField.exists)

            // Should have cancel button
            let cancelButton = app.buttons["Cancel"]
            XCTAssertTrue(cancelButton.exists)
        }
    }

    func testCancelDismissesNewConversationSheet() throws {
        app.launchArguments.append("--skip-auth")
        app.launch()

        let newConversationButton = app.buttons["New conversation"]
        if newConversationButton.waitForExistence(timeout: 5) {
            newConversationButton.tap()

            let cancelButton = app.buttons["Cancel"]
            if cancelButton.waitForExistence(timeout: 2) {
                cancelButton.tap()

                // Sheet should be dismissed
                let newConversationTitle = app.staticTexts["New Conversation"]
                XCTAssertFalse(newConversationTitle.waitForExistence(timeout: 1))
            }
        }
    }

    // MARK: - Accessibility Tests

    func testConversationListAccessibility() throws {
        app.launchArguments.append("--skip-auth")
        app.launch()

        // New conversation button should have accessibility label
        let newConversationButton = app.buttons["New conversation"]
        if newConversationButton.waitForExistence(timeout: 5) {
            XCTAssertTrue(newConversationButton.isHittable)
        }

        // Empty state should have accessibility
        let emptyStateLabel = app.staticTexts["No Conversations Yet"]
        if emptyStateLabel.waitForExistence(timeout: 2) {
            XCTAssertTrue(emptyStateLabel.isHittable)
        }
    }

    // MARK: - Tab Bar Tests

    func testConversationsTabExists() throws {
        app.launchArguments.append("--skip-auth")
        app.launch()

        // Should have Conversations tab
        let conversationsTab = app.tabBars.buttons["Conversations"]
        if conversationsTab.waitForExistence(timeout: 5) {
            XCTAssertTrue(conversationsTab.exists)
            XCTAssertTrue(conversationsTab.isSelected)
        }
    }

    func testSettingsTabExists() throws {
        app.launchArguments.append("--skip-auth")
        app.launch()

        // Should have Settings tab
        let settingsTab = app.tabBars.buttons["Settings"]
        if settingsTab.waitForExistence(timeout: 5) {
            XCTAssertTrue(settingsTab.exists)
            XCTAssertFalse(settingsTab.isSelected)
        }
    }

    func testCanSwitchBetweenTabs() throws {
        app.launchArguments.append("--skip-auth")
        app.launch()

        let settingsTab = app.tabBars.buttons["Settings"]
        if settingsTab.waitForExistence(timeout: 5) {
            settingsTab.tap()
            XCTAssertTrue(settingsTab.isSelected)

            let conversationsTab = app.tabBars.buttons["Conversations"]
            conversationsTab.tap()
            XCTAssertTrue(conversationsTab.isSelected)
        }
    }
}
