/**
 * API client for Dining Philosophers backend.
 */

import type {
  AuthResponse,
  Conversation,
  ConversationSummary,
  Message,
  Session,
  ThinkerProfile,
  ThinkerSuggestion,
  User,
  UserWithStats,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Token management
let accessToken: string | null = null;

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  if (accessToken) return accessToken;
  accessToken = localStorage.getItem('access_token');
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  if (typeof window !== 'undefined') {
    if (token) {
      localStorage.setItem('access_token', token);
    } else {
      localStorage.removeItem('access_token');
    }
  }
}

export function clearAuth(): void {
  accessToken = null;
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  }
}

export function getStoredUser(): User | null {
  if (typeof window === 'undefined') return null;
  const userJson = localStorage.getItem('user');
  if (!userJson) return null;
  try {
    return JSON.parse(userJson) as User;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User | null): void {
  if (typeof window !== 'undefined') {
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    } else {
      localStorage.removeItem('user');
    }
  }
}

async function fetchWithAuth<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const token = getAccessToken();
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Auth API
export async function register(
  username: string,
  displayName: string,
  password: string
): Promise<AuthResponse> {
  const response = await fetchWithAuth<AuthResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, display_name: displayName, password }),
  });
  setAccessToken(response.access_token);
  setStoredUser(response.user);
  return response;
}

export async function login(
  username: string,
  password: string
): Promise<AuthResponse> {
  const response = await fetchWithAuth<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  setAccessToken(response.access_token);
  setStoredUser(response.user);
  return response;
}

export async function logout(): Promise<void> {
  try {
    await fetchWithAuth<{ message: string }>('/api/auth/logout', {
      method: 'POST',
    });
  } finally {
    clearAuth();
  }
}

export async function getCurrentUser(): Promise<User | null> {
  const token = getAccessToken();
  if (!token) return null;
  try {
    return await fetchWithAuth<User>('/api/auth/me');
  } catch {
    clearAuth();
    return null;
  }
}

// Session API
export async function getSession(): Promise<Session | null> {
  const token = getAccessToken();
  if (!token) return null;
  try {
    return await fetchWithAuth<Session>('/api/sessions/me');
  } catch {
    return null;
  }
}

// Conversation API

// Backend response format for conversation list
interface BackendConversationSummary {
  id: string;
  session_id: string;
  topic: string;
  title: string | null;
  is_active: boolean;
  created_at: string;
  thinkers: Array<{
    name: string;
    bio: string;
    positions: string;
    style: string;
    color: string;
    image_url?: string | null;
  }>;
  message_count: number;
  total_cost: number;
}

export async function getConversations(): Promise<ConversationSummary[]> {
  const response =
    await fetchWithAuth<BackendConversationSummary[]>('/api/conversations');
  // Transform backend response to frontend ConversationSummary format
  return response.map((conv) => ({
    id: conv.id,
    topic: conv.topic,
    thinker_names: conv.thinkers.map((t) => t.name),
    thinkers: conv.thinkers.map((t) => ({
      name: t.name,
      image_url: t.image_url,
    })),
    message_count: conv.message_count,
    total_cost: conv.total_cost,
    created_at: conv.created_at,
    updated_at: conv.created_at, // Backend doesn't have updated_at yet
  }));
}

export async function getConversation(id: string): Promise<Conversation> {
  return fetchWithAuth<Conversation>(`/api/conversations/${id}`);
}

export interface ThinkerCreateData {
  name: string;
  bio: string;
  positions: string;
  style: string;
  color?: string;
  image_url?: string | null;
}

export interface CreateConversationData {
  topic: string;
  thinkers: ThinkerCreateData[];
}

export async function createConversation(
  data: CreateConversationData
): Promise<Conversation> {
  return fetchWithAuth<Conversation>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteConversation(id: string): Promise<void> {
  await fetchWithAuth<{ success: boolean }>(`/api/conversations/${id}`, {
    method: 'DELETE',
  });
}

// Message API
export async function sendMessage(
  conversationId: string,
  content: string
): Promise<Message> {
  return fetchWithAuth<Message>(
    `/api/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      body: JSON.stringify({ content }),
    }
  );
}

// Thinker API
export async function suggestThinkers(
  topic: string,
  count: number = 3,
  exclude: string[] = []
): Promise<ThinkerSuggestion[]> {
  return fetchWithAuth<ThinkerSuggestion[]>('/api/thinkers/suggest', {
    method: 'POST',
    body: JSON.stringify({ topic, count, exclude }),
  });
}

export interface ValidateThinkerResponse {
  valid: boolean;
  name: string;
  profile?: ThinkerProfile;
  error?: string;
}

export async function validateThinker(
  name: string
): Promise<ValidateThinkerResponse> {
  return fetchWithAuth<ValidateThinkerResponse>('/api/thinkers/validate', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

// Admin API
export async function getAdminUsers(): Promise<UserWithStats[]> {
  return fetchWithAuth<UserWithStats[]>('/api/admin/users');
}

export async function deleteUser(userId: string): Promise<{ message: string }> {
  return fetchWithAuth<{ message: string }>(`/api/admin/users/${userId}`, {
    method: 'DELETE',
  });
}

export interface UpdateSpendLimitResponse {
  user_id: string;
  spend_limit: number;
  message: string;
}

export async function updateUserSpendLimit(
  userId: string,
  spendLimit: number
): Promise<UpdateSpendLimitResponse> {
  return fetchWithAuth<UpdateSpendLimitResponse>(
    `/api/admin/users/${userId}/spend-limit`,
    {
      method: 'PATCH',
      body: JSON.stringify({ spend_limit: spendLimit }),
    }
  );
}

// Export for testing
export { API_BASE_URL };
