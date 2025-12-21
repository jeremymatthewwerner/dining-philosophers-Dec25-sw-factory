/**
 * Type definitions for Dining Philosophers frontend.
 * These mirror the backend Pydantic schemas.
 */

// Auth types
export interface User {
  id: string;
  username: string;
  display_name: string | null;
  is_admin: boolean;
  total_spend: number;
  spend_limit: number;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}

export interface UserWithStats extends User {
  conversation_count: number;
}

export interface SpendLimitError {
  currentSpend: number;
  spendLimit: number;
  message: string;
}

export interface Session {
  id: string;
  created_at: string;
}

export interface ThinkerProfile {
  name: string;
  bio: string;
  positions: string;
  style: string;
  image_url?: string | null;
}

export interface ThinkerSuggestion {
  name: string;
  reason: string;
  profile: ThinkerProfile;
}

export interface ConversationThinker {
  id: string;
  name: string;
  bio: string;
  positions: string;
  style: string;
  color: string;
  image_url?: string | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_type: 'user' | 'thinker' | 'system';
  sender_name: string | null;
  content: string;
  cost: number | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  session_id: string;
  topic: string;
  thinkers: ConversationThinker[];
  messages: Message[];
  total_cost: number;
  created_at: string;
  updated_at: string;
}

export interface ThinkerSummary {
  name: string;
  image_url?: string | null;
}

export interface ConversationSummary {
  id: string;
  topic: string;
  thinker_names: string[];
  thinkers: ThinkerSummary[];
  message_count: number;
  total_cost: number;
  created_at: string;
  updated_at: string;
}

// WebSocket message types
export type WSMessageType =
  | 'join'
  | 'leave'
  | 'user_message'
  | 'typing_start'
  | 'typing_stop'
  | 'message'
  | 'thinker_typing'
  | 'thinker_thinking'
  | 'thinker_stopped_typing'
  | 'user_joined'
  | 'user_left'
  | 'pause'
  | 'resume'
  | 'paused'
  | 'resumed'
  | 'set_speed'
  | 'speed_changed'
  | 'error';

export interface WSMessage {
  type: WSMessageType;
  conversation_id?: string;
  content?: string;
  sender_name?: string;
  sender_type?: 'user' | 'thinker';
  message_id?: string;
  timestamp?: string;
  cost?: number;
  speed_multiplier?: number;
}
