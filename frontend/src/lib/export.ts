/**
 * Export conversation to downloadable file formats.
 */

import type { Conversation, Message, ConversationThinker } from '@/types';

/**
 * Escapes HTML special characters to prevent XSS.
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/\n/g, '<br>');
}

/**
 * Escapes regex special characters.
 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Renders message content with highlighted mentions for HTML export.
 * Similar to the UI mention rendering but outputs HTML strings.
 */
function renderMentionsHtml(
  content: string,
  thinkers: ConversationThinker[]
): string {
  if (!thinkers || thinkers.length === 0) {
    return escapeHtml(content);
  }

  // Build a map of names to thinker data (case-insensitive)
  const thinkerMap = new Map<string, ConversationThinker>();
  thinkers.forEach((t) => {
    thinkerMap.set(t.name.toLowerCase(), t);
    // Also map individual name parts for partial matches
    const nameParts = t.name.split(' ');
    nameParts.forEach((part) => {
      if (part.length > 2) {
        thinkerMap.set(part.toLowerCase(), t);
      }
    });
  });

  // Create regex pattern matching any thinker name
  const names = Array.from(thinkerMap.keys()).sort(
    (a, b) => b.length - a.length
  );
  if (names.length === 0) return escapeHtml(content);

  const pattern = new RegExp(
    `\\b(${names.map(escapeRegex).join('|')})\\b`,
    'gi'
  );

  // Process content, escaping HTML and highlighting mentions
  const parts: string[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(content)) !== null) {
    // Add escaped text before this match
    if (match.index > lastIndex) {
      parts.push(escapeHtml(content.slice(lastIndex, match.index)));
    }

    // Add the highlighted mention
    const matchedName = match[1];
    const thinker = thinkerMap.get(matchedName.toLowerCase());
    if (thinker) {
      const color = thinker.color || '#6366f1';
      const avatarHtml = thinker.image_url
        ? `<img src="${thinker.image_url}" alt="${escapeHtml(thinker.name)}" class="mention-avatar">`
        : `<span class="mention-initial" style="background-color: ${color}20; color: ${color}">${thinker.name[0]}</span>`;
      parts.push(
        `<span class="mention" style="color: ${color}; background-color: ${color}15">${avatarHtml}${escapeHtml(matchedName)}</span>`
      );
    } else {
      parts.push(escapeHtml(matchedName));
    }

    lastIndex = match.index + matchedName.length;
  }

  // Add remaining escaped text
  if (lastIndex < content.length) {
    parts.push(escapeHtml(content.slice(lastIndex)));
  }

  return parts.join('');
}

/**
 * Formats a date for display.
 */
function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Generates a styled HTML document for the conversation.
 */
export function generateHtmlExport(
  conversation: Conversation,
  messages: Message[]
): string {
  const thinkerMap = new Map<string, ConversationThinker>();
  conversation.thinkers.forEach((t) => {
    thinkerMap.set(t.name, t);
  });

  const totalCost = messages.reduce((sum, m) => sum + (m.cost || 0), 0);
  const exportDate = new Date().toLocaleString();

  const messagesHtml = messages
    .map((msg) => {
      const isUser = msg.sender_type === 'user';
      const thinker = msg.sender_name ? thinkerMap.get(msg.sender_name) : null;
      const color = thinker?.color || '#6366f1';
      const time = formatDate(msg.created_at);
      const cost = msg.cost ? `$${msg.cost.toFixed(4)}` : '';

      if (isUser) {
        return `
          <div class="message user-message">
            <div class="message-bubble user-bubble">
              <div class="message-content">${renderMentionsHtml(msg.content, conversation.thinkers)}</div>
              <div class="message-meta">${time}</div>
            </div>
          </div>
        `;
      } else {
        return `
          <div class="message thinker-message">
            <div class="avatar" style="background-color: ${color}20; border-color: ${color}">
              ${thinker?.image_url ? `<img src="${thinker.image_url}" alt="${msg.sender_name}">` : `<span style="color: ${color}">${(msg.sender_name || '?')[0]}</span>`}
            </div>
            <div class="message-bubble thinker-bubble">
              <div class="sender-name" style="color: ${color}">${escapeHtml(msg.sender_name || 'Unknown')}</div>
              <div class="message-content">${renderMentionsHtml(msg.content, conversation.thinkers)}</div>
              <div class="message-meta">${time} ${cost ? `· ${cost}` : ''}</div>
            </div>
          </div>
        `;
      }
    })
    .join('\n');

  const thinkersHtml = conversation.thinkers
    .map(
      (t) => `
      <div class="thinker-card" style="border-left-color: ${t.color || '#6366f1'}">
        <div class="thinker-header">
          <div class="thinker-avatar" style="background-color: ${t.color || '#6366f1'}20">
            ${t.image_url ? `<img src="${t.image_url}" alt="${t.name}">` : `<span style="color: ${t.color || '#6366f1'}">${t.name[0]}</span>`}
          </div>
          <strong>${escapeHtml(t.name)}</strong>
        </div>
        <p class="thinker-bio">${escapeHtml(t.bio)}</p>
      </div>
    `
    )
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(conversation.topic)} - Dining Philosophers Export</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #18181b;
      color: #fafafa;
      line-height: 1.6;
      padding: 2rem;
      max-width: 900px;
      margin: 0 auto;
    }
    h1 { font-size: 1.75rem; margin-bottom: 0.5rem; }
    h2 { font-size: 1.25rem; color: #a1a1aa; margin: 2rem 0 1rem; border-bottom: 1px solid #3f3f46; padding-bottom: 0.5rem; }
    .header { margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #3f3f46; }
    .meta { color: #71717a; font-size: 0.875rem; margin-top: 0.5rem; }
    .thinkers { display: grid; gap: 1rem; margin-bottom: 2rem; }
    .thinker-card {
      background: #27272a;
      border-radius: 0.5rem;
      padding: 1rem;
      border-left: 3px solid;
    }
    .thinker-header { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }
    .thinker-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      overflow: hidden;
    }
    .thinker-avatar img { width: 100%; height: 100%; object-fit: cover; }
    .thinker-bio { color: #a1a1aa; font-size: 0.875rem; }
    .messages { display: flex; flex-direction: column; gap: 1rem; }
    .message { display: flex; gap: 0.75rem; }
    .user-message { justify-content: flex-end; }
    .thinker-message { justify-content: flex-start; }
    .avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      flex-shrink: 0;
      border: 2px solid;
      overflow: hidden;
    }
    .avatar img { width: 100%; height: 100%; object-fit: cover; }
    .message-bubble {
      max-width: 75%;
      padding: 0.75rem 1rem;
      border-radius: 1rem;
    }
    .user-bubble {
      background: #2563eb;
      border-bottom-right-radius: 0.25rem;
    }
    .thinker-bubble {
      background: #27272a;
      border-bottom-left-radius: 0.25rem;
    }
    .sender-name { font-weight: 600; font-size: 0.875rem; margin-bottom: 0.25rem; }
    .message-content { white-space: pre-wrap; }
    .mention {
      display: inline-flex;
      align-items: center;
      gap: 0.2rem;
      font-weight: 600;
      padding: 0.1rem 0.3rem;
      border-radius: 0.25rem;
      margin: 0 0.1rem;
    }
    .mention-avatar {
      width: 16px;
      height: 16px;
      border-radius: 50%;
      object-fit: cover;
    }
    .mention-initial {
      width: 16px;
      height: 16px;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: 600;
    }
    .message-meta { font-size: 0.75rem; color: #71717a; margin-top: 0.5rem; }
    .user-bubble .message-meta { color: #93c5fd; }
    .summary {
      background: #27272a;
      border-radius: 0.5rem;
      padding: 1rem;
      margin-top: 2rem;
    }
    .summary-row { display: flex; justify-content: space-between; padding: 0.25rem 0; }
    .summary-label { color: #a1a1aa; }
    @media print {
      body { background: white; color: black; }
      .thinker-bubble { background: #f4f4f5; }
      .summary { background: #f4f4f5; }
      .thinker-card { background: #f4f4f5; }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>${escapeHtml(conversation.topic)}</h1>
    <div class="meta">
      Exported from Dining Philosophers on ${exportDate}
    </div>
  </div>

  <h2>Participants</h2>
  <div class="thinkers">
    ${thinkersHtml}
  </div>

  <h2>Conversation</h2>
  <div class="messages">
    ${messagesHtml}
  </div>

  <div class="summary">
    <h2 style="margin-top: 0; border: none;">Summary</h2>
    <div class="summary-row">
      <span class="summary-label">Messages</span>
      <span>${messages.length}</span>
    </div>
    <div class="summary-row">
      <span class="summary-label">Total Cost</span>
      <span>$${totalCost.toFixed(4)}</span>
    </div>
    <div class="summary-row">
      <span class="summary-label">Started</span>
      <span>${formatDate(conversation.created_at)}</span>
    </div>
  </div>
</body>
</html>`;
}

/**
 * Generates a Markdown export of the conversation.
 */
export function generateMarkdownExport(
  conversation: Conversation,
  messages: Message[]
): string {
  const totalCost = messages.reduce((sum, m) => sum + (m.cost || 0), 0);
  const exportDate = new Date().toLocaleString();

  const thinkersSection = conversation.thinkers
    .map((t) => `### ${t.name}\n${t.bio}`)
    .join('\n\n');

  const messagesSection = messages
    .map((msg) => {
      const time = formatDate(msg.created_at);
      const sender =
        msg.sender_type === 'user' ? '**You**' : `**${msg.sender_name}**`;
      const cost = msg.cost ? ` ($${msg.cost.toFixed(4)})` : '';
      return `${sender} - ${time}${cost}\n\n${msg.content}`;
    })
    .join('\n\n---\n\n');

  return `# ${conversation.topic}

*Exported from Dining Philosophers on ${exportDate}*

## Participants

${thinkersSection}

## Conversation

${messagesSection}

---

## Summary

- **Messages:** ${messages.length}
- **Total Cost:** $${totalCost.toFixed(4)}
- **Started:** ${formatDate(conversation.created_at)}
`;
}

/**
 * Triggers a file download in the browser.
 */
export function downloadFile(
  content: string,
  filename: string,
  mimeType: string
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Exports conversation as HTML file.
 */
export function exportAsHtml(
  conversation: Conversation,
  messages: Message[]
): void {
  const html = generateHtmlExport(conversation, messages);
  const filename = `${conversation.topic.slice(0, 50).replace(/[^a-z0-9]/gi, '-')}-export.html`;
  downloadFile(html, filename, 'text/html');
}

/**
 * Exports conversation as Markdown file.
 */
export function exportAsMarkdown(
  conversation: Conversation,
  messages: Message[]
): void {
  const markdown = generateMarkdownExport(conversation, messages);
  const filename = `${conversation.topic.slice(0, 50).replace(/[^a-z0-9]/gi, '-')}-export.md`;
  downloadFile(markdown, filename, 'text/markdown');
}
