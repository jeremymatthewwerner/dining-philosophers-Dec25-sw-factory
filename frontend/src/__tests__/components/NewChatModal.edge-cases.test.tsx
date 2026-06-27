/**
 * Edge-case / error-path tests for NewChatModal.
 *
 * The base NewChatModal.test.tsx covers the happy path (open/close, topic ->
 * thinker selection, create). This file targets the error and edge branches
 * that were previously uncovered:
 *
 *  - Escape-key handler closing the modal (NewChatModal.tsx lines 82-84)
 *  - handleCreate error handling: network errors, generic Error messages,
 *    and non-Error rejections (lines 141-150)
 *  - handleSelectThinker auto-fetching a replacement suggestion after a
 *    selection, plus the silent-fail catch when that fetch rejects
 *    (lines 160-197)
 *  - handleRefreshSuggestion: successful replacement, the no-unique-result
 *    fallback that removes the stale suggestion, and the error path that
 *    surfaces a message (lines 206-250)
 */

import { fireEvent, render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import { NewChatModal } from '@/components/NewChatModal';
import type { ThinkerProfile, ThinkerSuggestion } from '@/types';

const createSuggestion = (name: string): ThinkerSuggestion => ({
  name,
  reason: `${name} would be great`,
  profile: {
    name,
    bio: `Bio of ${name}`,
    positions: 'Some positions',
    style: 'Some style',
  },
});

const baseProps = () => ({
  isOpen: true,
  onClose: jest.fn(),
  onCreate: jest.fn().mockResolvedValue(undefined),
  onSuggestThinkers: jest
    .fn()
    .mockResolvedValue([createSuggestion('Socrates')]),
  onValidateThinker: jest.fn().mockResolvedValue({
    name: 'Custom',
    bio: 'Bio',
    positions: 'Positions',
    style: 'Style',
  } as ThinkerProfile),
});

// Advance from the topic step into the thinker-selection step.
async function gotoThinkerStep(
  user: ReturnType<typeof userEvent.setup>,
  topic = 'Philosophy'
) {
  await user.type(screen.getByTestId('topic-input'), topic);
  await user.click(screen.getByTestId('next-button'));
  await waitFor(() => {
    expect(screen.getByText('Select Thinkers')).toBeInTheDocument();
  });
}

describe('NewChatModal edge cases', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Escape key handling', () => {
    it('closes the modal when Escape is pressed', () => {
      const onClose = jest.fn();
      render(<NewChatModal {...baseProps()} onClose={onClose} />);

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('ignores other keys', () => {
      const onClose = jest.fn();
      render(<NewChatModal {...baseProps()} onClose={onClose} />);

      fireEvent.keyDown(document, { key: 'Enter' });
      fireEvent.keyDown(document, { key: 'a' });

      expect(onClose).not.toHaveBeenCalled();
    });

    it('does not register the Escape listener when closed', () => {
      const onClose = jest.fn();
      render(
        <NewChatModal {...baseProps()} isOpen={false} onClose={onClose} />
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('handleCreate error handling', () => {
    it('shows a friendly network message when onCreate fails to fetch', async () => {
      const user = userEvent.setup();
      const onCreate = jest
        .fn()
        .mockRejectedValue(new Error('Failed to fetch'));

      render(<NewChatModal {...baseProps()} onCreate={onCreate} />);

      await gotoThinkerStep(user);
      await user.click(screen.getByTestId('accept-suggestion'));
      await user.click(screen.getByTestId('create-button'));

      await waitFor(() => {
        expect(
          screen.getByText(
            'Network error. Please check your connection and try again.'
          )
        ).toBeInTheDocument();
      });
      // Modal stays open on failure so the user can retry.
      expect(screen.getByTestId('new-chat-modal')).toBeInTheDocument();
    });

    it('recognizes "network" in the error message as a network failure', async () => {
      const user = userEvent.setup();
      const onCreate = jest
        .fn()
        .mockRejectedValue(new Error('A network problem occurred'));

      render(<NewChatModal {...baseProps()} onCreate={onCreate} />);

      await gotoThinkerStep(user);
      await user.click(screen.getByTestId('accept-suggestion'));
      await user.click(screen.getByTestId('create-button'));

      await waitFor(() => {
        expect(
          screen.getByText(
            'Network error. Please check your connection and try again.'
          )
        ).toBeInTheDocument();
      });
    });

    it('surfaces a non-network Error message verbatim', async () => {
      const user = userEvent.setup();
      const onCreate = jest
        .fn()
        .mockRejectedValue(new Error('Server exploded'));

      render(<NewChatModal {...baseProps()} onCreate={onCreate} />);

      await gotoThinkerStep(user);
      await user.click(screen.getByTestId('accept-suggestion'));
      await user.click(screen.getByTestId('create-button'));

      await waitFor(() => {
        expect(screen.getByText('Server exploded')).toBeInTheDocument();
      });
    });

    it('falls back to a default message for non-Error rejections', async () => {
      const user = userEvent.setup();
      // Reject with a non-Error value to exercise the `: t.errorCreateConversation` branch.
      const onCreate = jest.fn().mockRejectedValue('boom');

      render(<NewChatModal {...baseProps()} onCreate={onCreate} />);

      await gotoThinkerStep(user);
      await user.click(screen.getByTestId('accept-suggestion'));
      await user.click(screen.getByTestId('create-button'));

      await waitFor(() => {
        expect(
          screen.getByText('Failed to create conversation')
        ).toBeInTheDocument();
      });
    });
  });

  describe('handleSelectThinker auto-fetch replacement', () => {
    it('fetches and appends a fresh suggestion after a selection', async () => {
      const user = userEvent.setup();
      const onSuggestThinkers = jest.fn().mockImplementation((_t, count) => {
        // Initial batch (count === 5) vs the 1-item replacement fetch.
        if (count === 5) return Promise.resolve([createSuggestion('Socrates')]);
        return Promise.resolve([createSuggestion('Plato')]);
      });

      render(
        <NewChatModal {...baseProps()} onSuggestThinkers={onSuggestThinkers} />
      );

      await gotoThinkerStep(user);
      await user.click(screen.getByTestId('accept-suggestion'));

      // After selecting Socrates, a replacement (Plato) is requested with the
      // selected name excluded and added to the visible suggestions.
      await waitFor(() => {
        expect(onSuggestThinkers).toHaveBeenCalledWith(
          'Philosophy',
          1,
          expect.arrayContaining(['Socrates'])
        );
      });
      await waitFor(() => {
        expect(screen.getByText('Plato')).toBeInTheDocument();
      });
    });

    it('does not append a duplicate replacement suggestion', async () => {
      const user = userEvent.setup();
      // Replacement fetch returns a name already present -> deduped out.
      const onSuggestThinkers = jest.fn().mockImplementation((_t, count) => {
        if (count === 5) return Promise.resolve([createSuggestion('Socrates')]);
        return Promise.resolve([createSuggestion('Socrates')]);
      });

      render(
        <NewChatModal {...baseProps()} onSuggestThinkers={onSuggestThinkers} />
      );

      await gotoThinkerStep(user);
      await user.click(screen.getByTestId('accept-suggestion'));

      await waitFor(() => {
        expect(onSuggestThinkers).toHaveBeenCalledWith(
          'Philosophy',
          1,
          expect.anything()
        );
      });
      // Socrates was selected; no leftover Socrates suggestion remains visible.
      await waitFor(() => {
        expect(
          screen.queryByTestId('thinker-suggestion')
        ).not.toBeInTheDocument();
      });
    });

    it('silently ignores a failed replacement fetch', async () => {
      const user = userEvent.setup();
      const onSuggestThinkers = jest.fn().mockImplementation((_t, count) => {
        if (count === 5) return Promise.resolve([createSuggestion('Socrates')]);
        return Promise.reject(new Error('replacement fetch failed'));
      });

      render(
        <NewChatModal {...baseProps()} onSuggestThinkers={onSuggestThinkers} />
      );

      await gotoThinkerStep(user);
      await user.click(screen.getByTestId('accept-suggestion'));

      await waitFor(() => {
        expect(onSuggestThinkers).toHaveBeenCalledTimes(2);
      });
      // The failure is swallowed: no error banner, selection still succeeded.
      expect(
        screen.queryByText('replacement fetch failed')
      ).not.toBeInTheDocument();
      expect(screen.getByTestId('selected-thinker')).toBeInTheDocument();
    });
  });

  describe('handleRemoveThinker', () => {
    it('removes a previously selected thinker', async () => {
      const user = userEvent.setup();
      const onSuggestThinkers = jest.fn().mockImplementation((_t, count) => {
        if (count === 5) return Promise.resolve([createSuggestion('Socrates')]);
        return Promise.resolve([]);
      });

      render(
        <NewChatModal {...baseProps()} onSuggestThinkers={onSuggestThinkers} />
      );

      await gotoThinkerStep(user);
      await user.click(screen.getByTestId('accept-suggestion'));

      await waitFor(() => {
        expect(screen.getByTestId('selected-thinker')).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText('Remove Socrates'));

      await waitFor(() => {
        expect(
          screen.queryByTestId('selected-thinker')
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('handleRefreshSuggestion', () => {
    it('replaces a suggestion with a fresh unique one', async () => {
      const user = userEvent.setup();
      const onSuggestThinkers = jest.fn().mockImplementation((_t, count) => {
        if (count === 5) return Promise.resolve([createSuggestion('Socrates')]);
        return Promise.resolve([createSuggestion('Aristotle')]);
      });

      render(
        <NewChatModal {...baseProps()} onSuggestThinkers={onSuggestThinkers} />
      );

      await gotoThinkerStep(user);
      await waitFor(() => {
        expect(screen.getByTestId('refresh-suggestion')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('refresh-suggestion'));

      await waitFor(() => {
        expect(screen.getByText('Aristotle')).toBeInTheDocument();
      });
      expect(screen.queryByText('Socrates')).not.toBeInTheDocument();
    });

    it('removes the stale suggestion when no unique replacement is returned', async () => {
      const user = userEvent.setup();
      // Replacement returns the same name -> not unique -> stale removed.
      const onSuggestThinkers = jest.fn().mockImplementation((_t, count) => {
        if (count === 5) return Promise.resolve([createSuggestion('Socrates')]);
        return Promise.resolve([createSuggestion('Socrates')]);
      });

      render(
        <NewChatModal {...baseProps()} onSuggestThinkers={onSuggestThinkers} />
      );

      await gotoThinkerStep(user);
      await waitFor(() => {
        expect(screen.getByTestId('refresh-suggestion')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('refresh-suggestion'));

      // The non-unique replacement causes the original to be dropped.
      await waitFor(() => {
        expect(
          screen.queryByTestId('thinker-suggestion')
        ).not.toBeInTheDocument();
      });
    });

    it('surfaces an error message when the refresh fetch rejects', async () => {
      const user = userEvent.setup();
      const onSuggestThinkers = jest.fn().mockImplementation((_t, count) => {
        if (count === 5) return Promise.resolve([createSuggestion('Socrates')]);
        return Promise.reject(new Error('refresh boom'));
      });

      render(
        <NewChatModal {...baseProps()} onSuggestThinkers={onSuggestThinkers} />
      );

      await gotoThinkerStep(user);
      await waitFor(() => {
        expect(screen.getByTestId('refresh-suggestion')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('refresh-suggestion'));

      await waitFor(() => {
        expect(screen.getByText('refresh boom')).toBeInTheDocument();
      });
    });

    it('falls back to a default message for non-Error refresh rejections', async () => {
      const user = userEvent.setup();
      const onSuggestThinkers = jest.fn().mockImplementation((_t, count) => {
        if (count === 5) return Promise.resolve([createSuggestion('Socrates')]);
        return Promise.reject('plain string failure');
      });

      render(
        <NewChatModal {...baseProps()} onSuggestThinkers={onSuggestThinkers} />
      );

      await gotoThinkerStep(user);
      await waitFor(() => {
        expect(screen.getByTestId('refresh-suggestion')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('refresh-suggestion'));

      await waitFor(() => {
        expect(
          screen.getByText('Failed to get replacement suggestion')
        ).toBeInTheDocument();
      });
    });
  });
});
