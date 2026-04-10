/**
 * Tests for the components barrel export (src/components/index.ts).
 *
 * Verifies that all public components and types are exported correctly
 * through the barrel file, ensuring the import surface stays consistent.
 */

import * as ComponentsBarrel from '@/components';

describe('Components barrel exports', () => {
  it('exports ChatArea', () => {
    expect(ComponentsBarrel.ChatArea).toBeDefined();
    expect(typeof ComponentsBarrel.ChatArea).toBe('function');
  });

  it('exports ConversationList', () => {
    expect(ComponentsBarrel.ConversationList).toBeDefined();
    expect(typeof ComponentsBarrel.ConversationList).toBe('function');
  });

  it('exports CostMeter', () => {
    expect(ComponentsBarrel.CostMeter).toBeDefined();
    expect(typeof ComponentsBarrel.CostMeter).toBe('function');
  });

  it('exports ErrorBanner', () => {
    expect(ComponentsBarrel.ErrorBanner).toBeDefined();
    expect(typeof ComponentsBarrel.ErrorBanner).toBe('function');
  });

  it('exports FeedbackModal', () => {
    expect(ComponentsBarrel.FeedbackModal).toBeDefined();
    expect(typeof ComponentsBarrel.FeedbackModal).toBe('function');
  });

  it('exports MentionAutocomplete', () => {
    expect(ComponentsBarrel.MentionAutocomplete).toBeDefined();
    expect(typeof ComponentsBarrel.MentionAutocomplete).toBe('function');
  });

  it('exports filterThinkers utility from MentionAutocomplete', () => {
    expect(ComponentsBarrel.filterThinkers).toBeDefined();
    expect(typeof ComponentsBarrel.filterThinkers).toBe('function');
  });

  it('exports Message', () => {
    expect(ComponentsBarrel.Message).toBeDefined();
    expect(typeof ComponentsBarrel.Message).toBe('function');
  });

  it('exports MessageInput', () => {
    expect(ComponentsBarrel.MessageInput).toBeDefined();
    expect(typeof ComponentsBarrel.MessageInput).toBe('function');
  });

  it('exports MessageList', () => {
    expect(ComponentsBarrel.MessageList).toBeDefined();
    expect(typeof ComponentsBarrel.MessageList).toBe('function');
  });

  it('exports NewChatModal', () => {
    expect(ComponentsBarrel.NewChatModal).toBeDefined();
    expect(typeof ComponentsBarrel.NewChatModal).toBe('function');
  });

  it('exports ResizeDivider', () => {
    expect(ComponentsBarrel.ResizeDivider).toBeDefined();
    expect(typeof ComponentsBarrel.ResizeDivider).toBe('function');
  });

  it('exports Sidebar', () => {
    expect(ComponentsBarrel.Sidebar).toBeDefined();
    expect(typeof ComponentsBarrel.Sidebar).toBe('function');
  });

  it('exports SpendLimitBanner', () => {
    expect(ComponentsBarrel.SpendLimitBanner).toBeDefined();
    expect(typeof ComponentsBarrel.SpendLimitBanner).toBe('function');
  });

  it('exports StatusLine', () => {
    expect(ComponentsBarrel.StatusLine).toBeDefined();
    expect(typeof ComponentsBarrel.StatusLine).toBe('function');
  });

  it('exports ThinkerAvatar', () => {
    expect(ComponentsBarrel.ThinkerAvatar).toBeDefined();
    expect(typeof ComponentsBarrel.ThinkerAvatar).toBe('function');
  });

  it('exports ThinkerSelector', () => {
    expect(ComponentsBarrel.ThinkerSelector).toBeDefined();
    expect(typeof ComponentsBarrel.ThinkerSelector).toBe('function');
  });

  it('exports TypingIndicator', () => {
    expect(ComponentsBarrel.TypingIndicator).toBeDefined();
    expect(typeof ComponentsBarrel.TypingIndicator).toBe('function');
  });

  it('exports BuildInfo', () => {
    expect(ComponentsBarrel.BuildInfo).toBeDefined();
    expect(typeof ComponentsBarrel.BuildInfo).toBe('function');
  });
});
