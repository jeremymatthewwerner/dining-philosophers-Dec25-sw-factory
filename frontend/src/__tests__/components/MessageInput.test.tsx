import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MessageInput } from '@/components/MessageInput';

// Mock userEvent setup
const user = userEvent.setup();

describe('MessageInput', () => {
  it('renders input and send button', () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    expect(screen.getByTestId('message-input')).toBeInTheDocument();
    expect(screen.getByTestId('message-textarea')).toBeInTheDocument();
    expect(screen.getByTestId('send-button')).toBeInTheDocument();
  });

  it('calls onSend when form is submitted', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello, world!');
    await user.click(screen.getByTestId('send-button'));

    expect(onSend).toHaveBeenCalledWith('Hello, world!');
  });

  it('clears input after sending', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello!');
    await user.click(screen.getByTestId('send-button'));

    expect(textarea).toHaveValue('');
  });

  it('does not send empty message', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    await user.click(screen.getByTestId('send-button'));

    expect(onSend).not.toHaveBeenCalled();
  });

  it('does not send whitespace-only message', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, '   ');
    await user.click(screen.getByTestId('send-button'));

    expect(onSend).not.toHaveBeenCalled();
  });

  it('sends on Enter key (without Shift)', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello!');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    expect(onSend).toHaveBeenCalledWith('Hello!');
  });

  it('does not send on Shift+Enter', async () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'Hello!');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });

    expect(onSend).not.toHaveBeenCalled();
  });

  it('disables input when disabled prop is true', () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} disabled />);

    expect(screen.getByTestId('message-textarea')).toBeDisabled();
    expect(screen.getByTestId('send-button')).toBeDisabled();
  });

  it('shows custom placeholder', () => {
    const onSend = jest.fn();
    render(<MessageInput onSend={onSend} placeholder="Custom placeholder" />);

    expect(
      screen.getByPlaceholderText('Custom placeholder')
    ).toBeInTheDocument();
  });

  it('calls onTypingStart when user starts typing', async () => {
    const onSend = jest.fn();
    const onTypingStart = jest.fn();
    render(<MessageInput onSend={onSend} onTypingStart={onTypingStart} />);

    const textarea = screen.getByTestId('message-textarea');
    await user.type(textarea, 'H');

    expect(onTypingStart).toHaveBeenCalled();
  });
});
