import '@testing-library/jest-dom';

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

// Mock fetch for API calls
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({}),
  })
) as jest.Mock;

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  clear: jest.fn(),
  removeItem: jest.fn(),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock WebSocket with constants
const MockWebSocket = jest.fn().mockImplementation(() => ({
  readyState: 1, // WebSocket.OPEN
  onopen: null,
  onclose: null,
  onmessage: null,
  onerror: null,
  send: jest.fn(),
  close: jest.fn(),
}));

// Add WebSocket constants
Object.defineProperty(MockWebSocket, 'CONNECTING', { value: 0 });
Object.defineProperty(MockWebSocket, 'OPEN', { value: 1 });
Object.defineProperty(MockWebSocket, 'CLOSING', { value: 2 });
Object.defineProperty(MockWebSocket, 'CLOSED', { value: 3 });

global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
