/**
 * Integration-gap tests for FeedbackModal.
 *
 * The original FeedbackModal test suite covers the happy-path file upload,
 * validation errors, and submission flow, but leaves the screenshot
 * drag-and-drop, clipboard paste, FileReader error handling, and modal-close
 * cleanup paths untested (FeedbackModal.tsx branch coverage was ~55%).
 *
 * These tests exercise those user-facing integration flows end-to-end.
 */

import { fireEvent, render, screen, waitFor } from '@/test-utils';
import { FeedbackModal } from '@/components/FeedbackModal';
import * as api from '@/lib/api';

jest.mock('@/lib/api', () => ({
  ...jest.requireActual('@/lib/api'),
  submitFeedback: jest.fn(),
  getStoredUser: jest.fn(),
}));

const mockGetStoredUser = api.getStoredUser as jest.MockedFunction<
  typeof api.getStoredUser
>;

// Build a FileReader mock whose onload/onerror callbacks can be fired manually.
type FileReaderMock = {
  readAsDataURL: jest.Mock;
  result: string;
  onload: ((this: FileReader, ev: ProgressEvent<FileReader>) => unknown) | null;
  onerror:
    | ((this: FileReader, ev: ProgressEvent<FileReader>) => unknown)
    | null;
};

const installFileReaderMock = (): FileReaderMock => {
  const reader: FileReaderMock = {
    readAsDataURL: jest.fn(),
    result: 'data:image/png;base64,dGVzdA==',
    onload: null,
    onerror: null,
  };
  jest
    .spyOn(window, 'FileReader')
    .mockImplementation(() => reader as unknown as FileReader);
  return reader;
};

const createMockFile = (name: string, size: number, type: string): File => {
  const content = new Array(size).fill('a').join('');
  return new File([content], name, { type });
};

// Minimal clipboard item shaped like a DataTransferItem.
const makeClipboardItem = (type: string, file: File | null) => ({
  type,
  getAsFile: () => file,
});

const mockCreateObjectURL = jest.fn(() => 'blob:mock-url');
const mockRevokeObjectURL = jest.fn();

describe('FeedbackModal integration gaps', () => {
  const defaultProps = { isOpen: true, onClose: jest.fn() };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetStoredUser.mockReturnValue(null);
    URL.createObjectURL = mockCreateObjectURL;
    URL.revokeObjectURL = mockRevokeObjectURL;
  });

  describe('clipboard paste', () => {
    it('processes a pasted image and shows the preview', async () => {
      const reader = installFileReaderMock();
      render(<FeedbackModal {...defaultProps} />);

      const dropzone = screen.getByTestId('screenshot-dropzone');
      const file = createMockFile('pasted.png', 1000, 'image/png');

      fireEvent.paste(dropzone, {
        clipboardData: { items: [makeClipboardItem('image/png', file)] },
      });

      // Fire the FileReader onload to complete processing.
      reader.onload?.call(
        reader as unknown as FileReader,
        {} as ProgressEvent<FileReader>
      );

      await waitFor(() => {
        expect(screen.getByTestId('screenshot-preview')).toBeInTheDocument();
      });
      // The pasted file is renamed with a screenshot- timestamp prefix.
      expect(screen.getByText(/^screenshot-.*\.png$/)).toBeInTheDocument();
    });

    it('ignores a paste event with no clipboard items', () => {
      installFileReaderMock();
      render(<FeedbackModal {...defaultProps} />);

      const dropzone = screen.getByTestId('screenshot-dropzone');
      fireEvent.paste(dropzone, { clipboardData: { items: undefined } });

      // No preview should appear; dropzone stays visible.
      expect(
        screen.queryByTestId('screenshot-preview')
      ).not.toBeInTheDocument();
      expect(screen.getByTestId('screenshot-dropzone')).toBeInTheDocument();
    });

    it('ignores a paste event that contains only non-image items', () => {
      installFileReaderMock();
      render(<FeedbackModal {...defaultProps} />);

      const dropzone = screen.getByTestId('screenshot-dropzone');
      fireEvent.paste(dropzone, {
        clipboardData: { items: [makeClipboardItem('text/plain', null)] },
      });

      expect(
        screen.queryByTestId('screenshot-preview')
      ).not.toBeInTheDocument();
    });
  });

  describe('drag and drop', () => {
    it('highlights the dropzone on drag over and reverts on drag leave', () => {
      render(<FeedbackModal {...defaultProps} />);
      const dropzone = screen.getByTestId('screenshot-dropzone');

      // Drag over -> dragging state shows the "Drop image here" label.
      fireEvent.dragOver(dropzone);
      expect(screen.getByText('Drop image here')).toBeInTheDocument();

      // Drag leave to outside the dropzone -> reverts to default label.
      fireEvent.dragLeave(dropzone, { relatedTarget: document.body });
      expect(screen.getByText('Upload screenshot')).toBeInTheDocument();
    });

    it('processes a dropped image file', async () => {
      const reader = installFileReaderMock();
      render(<FeedbackModal {...defaultProps} />);
      const dropzone = screen.getByTestId('screenshot-dropzone');
      const file = createMockFile('dropped.png', 1000, 'image/png');

      fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });
      reader.onload?.call(
        reader as unknown as FileReader,
        {} as ProgressEvent<FileReader>
      );

      await waitFor(() => {
        expect(screen.getByText('dropped.png')).toBeInTheDocument();
      });
    });

    it('ignores a drop with no files', () => {
      installFileReaderMock();
      render(<FeedbackModal {...defaultProps} />);
      const dropzone = screen.getByTestId('screenshot-dropzone');

      fireEvent.drop(dropzone, { dataTransfer: { files: [] } });
      expect(
        screen.queryByTestId('screenshot-preview')
      ).not.toBeInTheDocument();
    });

    it('skips dropped files that are not allowed image types', () => {
      installFileReaderMock();
      render(<FeedbackModal {...defaultProps} />);
      const dropzone = screen.getByTestId('screenshot-dropzone');
      const file = createMockFile('notes.txt', 100, 'text/plain');

      fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });
      // Dropzone remains; no preview created for disallowed type.
      expect(
        screen.queryByTestId('screenshot-preview')
      ).not.toBeInTheDocument();
      expect(screen.getByTestId('screenshot-dropzone')).toBeInTheDocument();
    });
  });

  describe('FileReader error handling', () => {
    it('shows an error when the screenshot file cannot be read', async () => {
      const reader = installFileReaderMock();
      render(<FeedbackModal {...defaultProps} />);

      const input = screen.getByTestId('screenshot-input');
      const file = createMockFile('broken.png', 1000, 'image/png');
      fireEvent.change(input, { target: { files: [file] } });

      // Trigger the error callback instead of onload.
      reader.onerror?.call(
        reader as unknown as FileReader,
        {} as ProgressEvent<FileReader>
      );

      await waitFor(() => {
        expect(
          screen.getByText('Failed to read screenshot file')
        ).toBeInTheDocument();
      });
      // The preview object URL is revoked on error.
      expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    });
  });

  describe('file input edge cases', () => {
    it('handles a file-input change with no file selected (dialog cancelled)', () => {
      installFileReaderMock();
      render(<FeedbackModal {...defaultProps} />);

      // While no screenshot is set, the file input is mounted. Firing a change
      // with an empty file list (e.g. the user opened then cancelled the OS
      // file dialog) takes the no-file branch and leaves the dropzone in place.
      const input = screen.getByTestId('screenshot-input');
      fireEvent.change(input, { target: { files: [] } });

      expect(
        screen.queryByTestId('screenshot-preview')
      ).not.toBeInTheDocument();
      expect(screen.getByTestId('screenshot-dropzone')).toBeInTheDocument();
    });
  });

  describe('modal close cleanup', () => {
    it('revokes the screenshot object URL when the modal is closed', async () => {
      const reader = installFileReaderMock();
      const { rerender } = render(<FeedbackModal {...defaultProps} />);

      const input = screen.getByTestId('screenshot-input');
      const file = createMockFile('shot.png', 1000, 'image/png');
      fireEvent.change(input, { target: { files: [file] } });
      reader.onload?.call(
        reader as unknown as FileReader,
        {} as ProgressEvent<FileReader>
      );

      await waitFor(() => {
        expect(screen.getByText('shot.png')).toBeInTheDocument();
      });

      mockRevokeObjectURL.mockClear();

      // Closing the modal runs the reset effect, which revokes the preview URL.
      rerender(<FeedbackModal {...defaultProps} isOpen={false} />);

      await waitFor(() => {
        expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
      });
    });
  });
});
