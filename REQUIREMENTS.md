# Requirements Specification: Dining Philosophers

## 1. Product Vision

Create an engaging, educational chat experience where users can have real-time group discussions with AI simulations of history's greatest thinkers. The experience should feel authentic - as if you've gathered Socrates, Einstein, and Maya Angelou in a group chat to discuss consciousness, creativity, or any topic of interest.

## 2. Core Features

### 2.1 User Interface Structure
- Sidebar showing list of previous chats (similar to ChatGPT interface)
- Each chat shows preview/title in sidebar
  - Long conversation names should be truncated with ellipsis
  - On hover, show full name in tooltip
- Affordance to start a new chat prominently displayed
- Clean, familiar chat interface pattern
- **Cost meter**: Display running total of LLM costs incurred since page load

### 2.2 New Chat Creation Flow
1. User clicks "New Chat"
2. User specifies number of thinkers to include
3. User writes 1-2 sentences describing the topic/question for discussion
4. System suggests appropriate thinkers based on the topic
5. User can:
   - Accept suggested thinkers
   - Ask to swap any thinker for another suggestion
   - Override by typing a specific thinker's name (system confirms they're a real person)
6. Chat begins once thinker selection is confirmed

### 2.3 Thinker Selection & Suggestion
- System uses LLM to suggest thinkers based on the topic
- Suggestion criteria:
  - Diverse viewpoints (people who might disagree with each other)
  - Some relevance to topic preferred but not strictly required
  - Mix of eras/backgrounds when appropriate
- When user types a custom thinker name:
  - System uses LLM + web search to verify person is real
  - System retrieves biographical info to build thinker profile
- Thinker profiles (generated dynamically or cached) include:
  - Biographical summary
  - Known positions and beliefs
  - Communication style characteristics
  - Historical context/era
- Living and historical figures both allowed

### 2.4 Thinker Behavior & Personality
- **Language**: All thinkers communicate in modern English regardless of era
- **Novel topics**: When addressing topics that didn't exist in their time, thinkers:
  - Apply their known philosophical/intellectual frameworks
  - Explicitly acknowledge the anachronism (e.g., "In my era we didn't have computers, but...")
- **Authenticity vs. creativity**:
  - LLM should reason about how the person would likely respond
  - Can be speculative/generative for engaging conversation
  - Not strictly limited to documented historical positions
- **Interaction style**:
  - Thinkers engage with each other, not just the user
  - They may agree, disagree, build on ideas, or challenge each other
  - Personality should feel consistent throughout conversation

### 2.5 Real-Time Chat Experience
- Messages appear in real-time as thinkers "type"
- Multiple thinkers can compose/send messages concurrently
- Typing indicators show when thinkers are composing
- **Thinking preview display**:
  - When thinkers are thinking, a preview of their thought process is shown
  - Thinking should sound like authentic inner monologue, not LLM reasoning
  - Only display when there's enough content to be meaningful (not truncated fragments)
  - Update frequency scales with pace setting (slower pace = less frequent updates)
  - Text should not be cut off mid-word; truncate at word/sentence boundaries
- Natural conversation flow:
  - Thinkers respond to each other, not just the user
  - Agreements, disagreements, and building on ideas
  - Occasional tangents and diversions (as real conversations have)
  - Variable response times (some thinkers more verbose, some more terse)
- **Active window model**:
  - Conversation only progresses when user has the chat open/focused
  - When user navigates away, conversation pauses (no background messages)
  - When user returns/visits a chat, thinkers automatically resume typing/responding

### 2.6 User Participation
- User can send messages at any time
- User messages are visible to all thinker agents
- Thinkers respond to and engage with user contributions
- User can steer the conversation with questions or topic shifts

### 2.7 Conversation Management
- Ability to pause/resume conversations
- Save conversation history
- Export conversations (text, markdown, etc.)
- Start new topic in same room or create new room

## 3. Non-Functional Requirements

### 3.1 Performance
- Low latency message delivery (<500ms)
- Support concurrent agent responses without blocking
- Graceful handling of LLM API rate limits

### 3.2 User Experience
- Clean, intuitive chat interface
- Mobile-responsive design
- Accessible (screen reader compatible, keyboard navigation)
- Clear visual distinction between different thinkers

### 3.3 Safety & Ethics
- Clear disclaimer that these are AI simulations, not actual people
- Content moderation for user inputs
- Responsible handling of controversial topics/figures
- Avoid putting harmful statements in historical figures' mouths

### 3.4 Scalability
- Support multiple concurrent users/chat rooms
- Efficient LLM token usage
- Consider caching for common responses/patterns

## 4. Technical Requirements

### 4.1 Agent Architecture
- Each thinker implemented as independent agent
- Agents maintain conversation context
- Agents have access to their thinker profile/persona
- Agents can "see" all messages and decide when/how to respond

### 4.2 Concurrency Model
- Parallel agent execution for realistic multi-party feel
- Coordination mechanism to prevent response flooding
- Natural timing/pacing algorithms

### 4.3 Natural Conversation Dynamics

The goal is to make thinker responses feel like a real group chat, not a mechanical round-robin.

#### 4.3.1 Response Length and Message Splitting
Real chat messages are typically short. Long paragraphs feel unnatural in a chat context.

**Message splitting**: Instead of sending one long message, thinkers should split responses into multiple chat bubbles:
- **Target**: Most messages should be 1-2 sentences (one chat bubble)
- **Splitting strategy**: When the LLM generates a longer response, split it at natural boundaries:
  - Sentence endings
  - Paragraph breaks
  - Thought transitions (e.g., "But...", "However...", "On the other hand...")
- **Timing between bubbles**: 1-3 seconds of "typing" delay between consecutive bubbles from same thinker
- **Interleaving allowed**: Another thinker (or user) may interject between a thinker's bubbles, creating natural conversation flow
- **Implementation**: Generate full response, then split and send as separate messages with delays

**Response styles**:
- **Quick reactions**: Just a few words (1 bubble)
  - "I couldn't agree more."
  - "That's precisely my concern."
  - "Interesting—but have you considered the inverse?"
- **Substantive responses**: 2-4 sentences split across 1-2 bubbles
- **Extended thoughts**: Longer explorations split across 2-4 bubbles with natural pauses

#### 4.3.2 Thinking Preview (Streaming Extended Thinking)
Instead of showing just "Thinking...", stream the LLM's actual reasoning process in real-time:
- **Use Claude's extended thinking feature** to capture genuine model reasoning
- **Stream thinking tokens** via WebSocket as they're generated
- Display thinking content with a typewriter effect, updating as new tokens arrive
- Examples of real thinking that might appear:
  - "Let me consider how Kant's categorical imperative applies here..."
  - "The user raises an interesting point about consciousness. I should address..."
  - "I disagree with what Aristotle just said because..."
- **Implementation details**:
  - Enable `thinking` parameter with appropriate budget in Claude API calls
  - Stream `thinking` block content via `thinker_thinking` WebSocket messages
  - Frontend accumulates and displays thinking tokens in real-time
  - Transition to response streaming once thinking completes
- **Styling**: Thinking text should be italicized and visually distinct from final messages
- **Benefits**: Shows authentic LLM reasoning, not canned phrases; more engaging waiting experience

#### 4.3.3 Response Timing Variation
Break the "everyone responds in order" pattern:
- **Silent turns**: A thinker may stay quiet for several exchanges if they have nothing to add
- **Consecutive messages**: Same thinker might send 2 bubbles in a row (initial thought, then follow-up)
- **Variable delays**:
  - Quick reactions: 2-5 seconds for short agreement/disagreement
  - Thoughtful responses: 10-30 seconds for substantive contributions
  - Longer pauses: Sometimes 30-60 seconds of apparent "thinking" before responding
- **Engagement triggers**: Higher probability of responding when:
  - Directly addressed by name
  - Topic relates closely to their expertise
  - They disagree with something said
  - Building on their own previous point

#### 4.3.4 Conversation Flow Patterns
Model realistic group chat dynamics:
- **Back-and-forth exchanges**: Two thinkers might have a brief direct exchange
- **Pile-on agreement**: Multiple thinkers quickly agreeing on a point
- **Debate clusters**: Disagreements that draw multiple participants
- **Topic drift**: Natural tangents that emerge from the conversation
- **Re-centering**: Occasionally a thinker brings conversation back to the original question

#### 4.3.5 Mention Highlighting
When a thinker or user mentions another participant by name, highlight the mention visually:
- **Detection**: Parse message content for participant names (case-insensitive)
- **Visual treatment**:
  - Apply distinct styling to mentioned names (bold, colored, or highlighted background)
  - Display the mentioned person's avatar/icon inline next to their name
  - Make mentions clickable (future: scroll to that person's last message)
- **Examples**:
  - "I agree with **[🖼️] Socrates** on this point" (with Socrates' avatar inline)
  - "What do you think, **[🖼️] Einstein**?" (with Einstein's avatar inline)
- **Implementation**: Process message content on render, detect names, wrap in styled component with avatar

### 4.4 LLM Integration
- Robust prompt engineering for persona consistency
- Context window management for long conversations
- Fallback handling for API failures

## 5. Future Considerations (Out of Initial Scope)

- User authentication (email/OAuth) - MVP uses local storage/anonymous sessions
- Custom thinker creation
- Voice synthesis for thinker responses
- Debate mode with structured formats
- Educational integrations (classroom use)
- Mobile apps

## 6. Open Questions

- [x] What tech stack best supports the real-time, concurrent agent requirement?
  - **Decided**: Next.js frontend, FastAPI backend, PostgreSQL, WebSockets
- [x] How do we handle thinkers from different eras/languages authentically?
  - **Decided**: All thinkers communicate in modern English for accessibility
- [x] What's the right balance of historical accuracy vs. engaging conversation?
  - **Decided**: Thinkers can be speculative/creative for engagement. LLM should reason about how the person might respond but can be generative rather than strictly historical.
- [x] How do we handle topics the historical figure never addressed?
  - **Decided**: Apply known frameworks to new concepts, with explicit acknowledgment (e.g., "In my time we didn't have X, but applying my views on Y...")
- [x] Pricing/usage model for LLM costs?
  - **Decided**: Monitor and see. Display a cost meter in the UI showing cost incurred since page load.
