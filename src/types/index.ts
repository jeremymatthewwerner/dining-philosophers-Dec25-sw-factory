export interface Philosopher {
  id: string;
  name: string;
  era: 'Ancient' | 'Medieval' | 'Early Modern' | 'Modern' | 'Contemporary';
  specialty: string[];
  systemPrompt: string;
  avatarUrl: string;
  greeting: string;
}

export interface Message {
  id: string;
  conversationId: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'down';
  timestamp: string;
  database: 'connected' | 'disconnected';
  websocket: 'active' | 'inactive';
}
