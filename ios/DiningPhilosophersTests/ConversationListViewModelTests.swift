// ConversationListViewModelTests.swift
// Tests for ConversationListViewModel
//
// Created by iOS Native Agent

@testable import DiningPhilosophers
import XCTest

final class ConversationListViewModelTests: XCTestCase {
    // MARK: - Initial State Tests

    func testInitialState() {
        let viewModel = ConversationListViewModel()

        XCTAssertTrue(viewModel.conversations.isEmpty, "Conversations should start empty")
        XCTAssertFalse(viewModel.isLoading, "Should not be loading initially")
        XCTAssertFalse(viewModel.isDeleting, "Should not be deleting initially")
        XCTAssertNil(viewModel.errorMessage, "Error message should be nil initially")
    }

    // MARK: - Error Handling Tests

    func testClearError() {
        let viewModel = ConversationListViewModel()

        // The errorMessage is var, so we can set it for testing
        viewModel.errorMessage = "Test error"
        XCTAssertNotNil(viewModel.errorMessage)

        viewModel.clearError()
        XCTAssertNil(viewModel.errorMessage, "Error should be cleared")
    }

    // MARK: - Model Tests

    func testConversationSummaryDisplayTitle() {
        // Test with title
        let withTitle = createTestConversationSummary(id: "1", topic: "Test Topic", title: "Custom Title")
        XCTAssertEqual(withTitle.displayTitle, "Custom Title")

        // Test without title (falls back to topic)
        let withoutTitle = createTestConversationSummary(id: "2", topic: "Topic Only", title: nil)
        XCTAssertEqual(withoutTitle.displayTitle, "Topic Only")
    }

    func testConversationSummaryThinkerNames() {
        let summary = createTestConversationSummary(
            id: "1",
            topic: "Philosophy",
            title: nil,
            thinkers: [
                createTestThinker(id: "t1", name: "Socrates"),
                createTestThinker(id: "t2", name: "Plato"),
                createTestThinker(id: "t3", name: "Aristotle")
            ]
        )

        XCTAssertEqual(summary.thinkerNames, ["Socrates", "Plato", "Aristotle"])
    }

    func testConversationSummaryHashable() {
        let summary1 = createTestConversationSummary(id: "same-id", topic: "Topic 1", title: nil)
        let summary2 = createTestConversationSummary(id: "same-id", topic: "Topic 2", title: "Different")

        // Same ID should be equal (Hashable based on ID)
        XCTAssertEqual(summary1, summary2)

        let summary3 = createTestConversationSummary(id: "different-id", topic: "Topic 1", title: nil)
        XCTAssertNotEqual(summary1, summary3)
    }

    // MARK: - ThinkerListItem Tests

    func testThinkerListItemDecoding() throws {
        let json = """
        {
            "id": "thinker-123",
            "conversation_id": "conv-456",
            "name": "Socrates",
            "bio": "Ancient Greek philosopher",
            "positions": "I know that I know nothing",
            "style": "Questioning",
            "color": "#6366f1",
            "image_url": "https://example.com/socrates.jpg",
            "created_at": "2024-01-15T10:30:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let thinker = try decoder.decode(ThinkerListItem.self, from: Data(json.utf8))

        XCTAssertEqual(thinker.id, "thinker-123")
        XCTAssertEqual(thinker.conversationId, "conv-456")
        XCTAssertEqual(thinker.name, "Socrates")
        XCTAssertEqual(thinker.bio, "Ancient Greek philosopher")
        XCTAssertEqual(thinker.color, "#6366f1")
        XCTAssertEqual(thinker.imageUrl, "https://example.com/socrates.jpg")
    }

    func testThinkerListItemDecodingWithoutOptionalFields() throws {
        let json = """
        {
            "id": "thinker-123",
            "conversation_id": "conv-456",
            "name": "Plato",
            "bio": "Student of Socrates",
            "positions": "Theory of Forms",
            "style": "Dialectic",
            "color": "#ec4899",
            "image_url": null,
            "created_at": "2024-01-15T10:30:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let thinker = try decoder.decode(ThinkerListItem.self, from: Data(json.utf8))

        XCTAssertEqual(thinker.name, "Plato")
        XCTAssertNil(thinker.imageUrl)
    }

    // MARK: - ConversationSummary Decoding Tests

    func testConversationSummaryDecoding() throws {
        let json = """
        {
            "id": "conv-123",
            "session_id": "session-456",
            "topic": "What is justice?",
            "title": "Dialogue on Justice",
            "is_active": true,
            "created_at": "2024-01-15T10:30:00Z",
            "thinkers": [
                {
                    "id": "t1",
                    "conversation_id": "conv-123",
                    "name": "Socrates",
                    "bio": "Greek philosopher",
                    "positions": "Virtue ethics",
                    "style": "Questioning",
                    "color": "#6366f1",
                    "image_url": null,
                    "created_at": "2024-01-15T10:30:00Z"
                }
            ],
            "message_count": 42,
            "total_cost": 0.05
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let summary = try decoder.decode(ConversationSummary.self, from: Data(json.utf8))

        XCTAssertEqual(summary.id, "conv-123")
        XCTAssertEqual(summary.sessionId, "session-456")
        XCTAssertEqual(summary.topic, "What is justice?")
        XCTAssertEqual(summary.title, "Dialogue on Justice")
        XCTAssertTrue(summary.isActive)
        XCTAssertEqual(summary.messageCount, 42)
        XCTAssertEqual(summary.totalCost, 0.05, accuracy: 0.001)
        XCTAssertEqual(summary.thinkers.count, 1)
        XCTAssertEqual(summary.thinkers.first?.name, "Socrates")
    }

    // MARK: - Helper Methods

    private func createTestConversationSummary(
        id: String,
        topic: String,
        title: String?,
        thinkers: [ThinkerListItem] = []
    ) -> ConversationSummary {
        ConversationSummary(
            id: id,
            sessionId: "test-session",
            topic: topic,
            title: title,
            isActive: true,
            createdAt: Date(),
            thinkers: thinkers,
            messageCount: 0,
            totalCost: 0.0
        )
    }

    private func createTestThinker(id: String, name: String) -> ThinkerListItem {
        ThinkerListItem(
            id: id,
            conversationId: "test-conv",
            name: name,
            bio: "Test bio",
            positions: "Test positions",
            style: "Test style",
            color: "#6366f1",
            imageUrl: nil,
            createdAt: Date()
        )
    }
}
