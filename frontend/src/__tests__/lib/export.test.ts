/**
 * Tests for the export utility functions.
 */

import type { Conversation, Message } from '@/types';
import {
  generateHtmlExport,
  generateMarkdownExport,
  downloadFile,
} from '@/lib/export';

describe('Export utilities', () => {
  const mockConversation: Conversation = {
    id: 'conv-1',
    session_id: 'session-1',
    topic: 'Philosophy Discussion',
    thinkers: [
      {
        id: 'thinker-1',
        name: 'Socrates',
        bio: 'Ancient Greek philosopher',
        positions: 'Socratic method',
        style: 'Questioning',
        color: '#3B82F6',
      },
      {
        id: 'thinker-2',
        name: 'Aristotle',
        bio: 'Student of Plato',
        positions: 'Logic and ethics',
        style: 'Systematic',
        color: '#10B981',
      },
    ],
    messages: [],
    created_at: '2024-01-01T12:00:00Z',
    updated_at: '2024-01-01T12:30:00Z',
    total_cost: 0.0123,
  };

  const mockMessages: Message[] = [
    {
      id: 'msg-1',
      conversation_id: 'conv-1',
      sender_type: 'user',
      sender_name: 'Jeremy',
      content: 'What is the nature of knowledge?',
      cost: null,
      created_at: '2024-01-01T12:00:00Z',
    },
    {
      id: 'msg-2',
      conversation_id: 'conv-1',
      sender_type: 'thinker',
      sender_name: 'Socrates',
      content: 'Ah, a fundamental question! Let us examine what we truly know.',
      cost: 0.0045,
      created_at: '2024-01-01T12:01:00Z',
    },
    {
      id: 'msg-3',
      conversation_id: 'conv-1',
      sender_type: 'thinker',
      sender_name: 'Aristotle',
      content: 'Knowledge must be grounded in observation and reason.',
      cost: 0.0078,
      created_at: '2024-01-01T12:02:00Z',
    },
  ];

  describe('generateHtmlExport', () => {
    it('generates valid HTML document', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<html lang="en">');
      expect(html).toContain('</html>');
    });

    it('includes conversation topic in title', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('<title>Philosophy Discussion');
      expect(html).toContain('<h1>Philosophy Discussion</h1>');
    });

    it('includes all thinker profiles', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('Socrates');
      expect(html).toContain('Ancient Greek philosopher');
      expect(html).toContain('Aristotle');
      expect(html).toContain('Student of Plato');
    });

    it('includes all messages', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('What is the nature of knowledge?');
      expect(html).toContain('Let us examine what we truly know');
      expect(html).toContain('Knowledge must be grounded in observation');
    });

    it('includes message costs for thinker messages', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('$0.0045');
      expect(html).toContain('$0.0078');
    });

    it('includes total cost in summary', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('Total Cost');
      // Total: 0.0045 + 0.0078 = 0.0123
      expect(html).toContain('$0.0123');
    });

    it('includes message count in summary', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('Messages');
      expect(html).toContain('>3<');
    });

    it('escapes HTML special characters', () => {
      const messagesWithHtml: Message[] = [
        {
          id: 'msg-1',
          conversation_id: 'conv-1',
          sender_type: 'user',
          sender_name: null,
          content: '<script>alert("xss")</script>',
          cost: null,
          created_at: '2024-01-01T12:00:00Z',
        },
      ];

      const html = generateHtmlExport(mockConversation, messagesWithHtml);

      expect(html).not.toContain('<script>');
      expect(html).toContain('&lt;script&gt;');
    });

    it('uses thinker colors for styling', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('#3B82F6');
      expect(html).toContain('#10B981');
    });

    it('applies dark theme styles', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('background: #18181b');
      expect(html).toContain('color: #fafafa');
    });

    it('includes print media styles', () => {
      const html = generateHtmlExport(mockConversation, mockMessages);

      expect(html).toContain('@media print');
    });
  });

  describe('generateMarkdownExport', () => {
    it('includes conversation topic as heading', () => {
      const md = generateMarkdownExport(mockConversation, mockMessages);

      expect(md).toContain('# Philosophy Discussion');
    });

    it('includes export date', () => {
      const md = generateMarkdownExport(mockConversation, mockMessages);

      expect(md).toContain('*Exported from Dining Philosophers on');
    });

    it('includes participants section', () => {
      const md = generateMarkdownExport(mockConversation, mockMessages);

      expect(md).toContain('## Participants');
      expect(md).toContain('### Socrates');
      expect(md).toContain('Ancient Greek philosopher');
      expect(md).toContain('### Aristotle');
    });

    it('includes all messages with sender info', () => {
      const md = generateMarkdownExport(mockConversation, mockMessages);

      expect(md).toContain('**You**');
      expect(md).toContain('What is the nature of knowledge?');
      expect(md).toContain('**Socrates**');
      expect(md).toContain('**Aristotle**');
    });

    it('includes message costs for thinkers', () => {
      const md = generateMarkdownExport(mockConversation, mockMessages);

      expect(md).toContain('($0.0045)');
      expect(md).toContain('($0.0078)');
    });

    it('includes summary section', () => {
      const md = generateMarkdownExport(mockConversation, mockMessages);

      expect(md).toContain('## Summary');
      expect(md).toContain('**Messages:** 3');
      expect(md).toContain('**Total Cost:** $0.0123');
    });

    it('separates messages with horizontal rules', () => {
      const md = generateMarkdownExport(mockConversation, mockMessages);

      expect(md).toContain('---');
    });
  });

  describe('downloadFile', () => {
    beforeEach(() => {
      // Mock URL.createObjectURL and URL.revokeObjectURL
      global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
      global.URL.revokeObjectURL = jest.fn();

      // Mock document.createElement and element methods
      const mockLink = {
        href: '',
        download: '',
        click: jest.fn(),
      } as unknown as HTMLAnchorElement;
      jest.spyOn(document, 'createElement').mockReturnValue(mockLink);
      jest
        .spyOn(document.body, 'appendChild')
        .mockImplementation(() => mockLink);
      jest
        .spyOn(document.body, 'removeChild')
        .mockImplementation(() => mockLink);
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('creates a blob with correct content and mime type', () => {
      const content = 'Test content';
      const filename = 'test.txt';
      const mimeType = 'text/plain';

      downloadFile(content, filename, mimeType);

      expect(URL.createObjectURL).toHaveBeenCalled();
      const blobArg = (URL.createObjectURL as jest.Mock).mock.calls[0][0];
      expect(blobArg).toBeInstanceOf(Blob);
    });

    it('sets download filename on link', () => {
      const content = 'Test content';
      const filename = 'export.html';
      const mimeType = 'text/html';

      const mockLink = { href: '', download: '', click: jest.fn() };
      (document.createElement as jest.Mock).mockReturnValue(mockLink);

      downloadFile(content, filename, mimeType);

      expect(mockLink.download).toBe(filename);
    });

    it('triggers click on link', () => {
      const mockLink = { href: '', download: '', click: jest.fn() };
      (document.createElement as jest.Mock).mockReturnValue(mockLink);

      downloadFile('content', 'file.txt', 'text/plain');

      expect(mockLink.click).toHaveBeenCalled();
    });

    it('cleans up by revoking object URL', () => {
      downloadFile('content', 'file.txt', 'text/plain');

      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    });
  });
});
