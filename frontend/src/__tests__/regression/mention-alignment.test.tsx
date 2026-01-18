/**
 * Regression tests for @mention badge vertical alignment (Issue #493, PR #494)
 *
 * Bug: @mention badges appeared a few pixels higher than surrounding text,
 * creating visual misalignment.
 *
 * Fix: Added verticalAlign: 'text-bottom' to the span containing @mention badges
 * to align them with the text baseline of surrounding content.
 */

import { render } from '@/test-utils';
import { Message } from '@/components/Message';
import type { Message as MessageType, ConversationThinker } from '@/types';

describe('Mention Badge Vertical Alignment Regression', () => {
  const mockThinker: ConversationThinker = {
    id: '1',
    name: 'Socrates',
    bio: 'Ancient Greek philosopher',
    positions: 'Socratic method',
    style: 'Questioning',
    color: '#6366f1',
    image_url: null,
  };

  const createMessage = (content: string): MessageType => ({
    id: '1',
    conversation_id: 'conv-1',
    sender_type: 'user',
    sender_name: null,
    content,
    created_at: new Date().toISOString(),
    cost: null,
  });

  test('mention badge has verticalAlign: text-bottom style', () => {
    /**
     * Regression test for issue #493 (commit 66f7f3c):
     * - Bug: @mention badges appeared higher than surrounding text
     * - Fix: Added verticalAlign: 'text-bottom' to span
     * - Validates: Mention spans have the correct CSS property
     */
    const message = createMessage('What do you think, Socrates?');
    const { container } = render(
      <Message message={message} allThinkers={[mockThinker]} />
    );

    // Find the mention span - it has inline-flex and items-center classes
    const mentionSpan = container.querySelector(
      'span.inline-flex.items-center'
    );

    // Verify the span exists (the mention was rendered)
    expect(mentionSpan).toBeInTheDocument();

    // CRITICAL: Verify the verticalAlign style is set to 'text-bottom'
    expect(mentionSpan).toHaveStyle({ verticalAlign: 'text-bottom' });
  });

  test('mention badge alignment with multiple mentions', () => {
    /**
     * Edge case: Multiple @mentions in the same message should all have correct alignment.
     */
    const message = createMessage('Both Socrates and Plato would agree.');
    const plato: ConversationThinker = {
      id: '2',
      name: 'Plato',
      bio: 'Student of Socrates',
      positions: 'Theory of Forms',
      style: 'Dialogues',
      color: '#ec4899',
      image_url: null,
    };

    const { container } = render(
      <Message message={message} allThinkers={[mockThinker, plato]} />
    );

    // Find all mention spans (including the ThinkerAvatar which also has inline-flex)
    // We need to count only spans with content (thinker names)
    const mentionSpans = Array.from(
      container.querySelectorAll('span.inline-flex.items-center')
    ).filter((span) => span.textContent?.trim().length ?? 0 > 0);

    // Should have 2 mention spans (Socrates and Plato)
    expect(mentionSpans.length).toBeGreaterThanOrEqual(2);

    // All mentions should have correct vertical alignment
    mentionSpans.forEach((span) => {
      expect(span).toHaveStyle({ verticalAlign: 'text-bottom' });
    });
  });

  test('mention badge alignment in long text', () => {
    /**
     * Edge case: Mentions embedded in long text should maintain alignment.
     */
    const message = createMessage(
      'In a lengthy discussion about philosophy, Socrates made an important point.'
    );

    const { container } = render(
      <Message message={message} allThinkers={[mockThinker]} />
    );

    const mentionSpan = container.querySelector(
      'span.inline-flex.items-center'
    );

    expect(mentionSpan).toBeInTheDocument();
    expect(mentionSpan).toHaveStyle({ verticalAlign: 'text-bottom' });
  });

  test('mention badge style includes color and background', () => {
    /**
     * Verify the complete style object includes both the fix and original properties.
     */
    const message = createMessage('Hello Socrates!');

    const { container } = render(
      <Message message={message} allThinkers={[mockThinker]} />
    );

    const mentionSpan = container.querySelector(
      'span.inline-flex.items-center'
    );

    expect(mentionSpan).toBeInTheDocument();

    // Verify all style properties are present
    expect(mentionSpan).toHaveStyle({
      color: mockThinker.color,
      backgroundColor: `${mockThinker.color}15`,
      verticalAlign: 'text-bottom', // The regression fix
    });
  });
});
