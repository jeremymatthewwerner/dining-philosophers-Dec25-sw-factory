'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { User } from '@/types';
import * as api from '@/lib/api';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    displayName: string,
    password: string
  ) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing auth on mount
  useEffect(() => {
    const checkAuth = async () => {
      // First check localStorage for cached user
      const storedUser = api.getStoredUser();
      if (storedUser) {
        setUser(storedUser);
      }

      // Verify token is still valid
      const currentUser = await api.getCurrentUser();
      if (currentUser) {
        setUser(currentUser);
        api.setStoredUser(currentUser);
      } else {
        setUser(null);
      }
      setIsLoading(false);
    };
    checkAuth();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await api.login(username, password);
    setUser(response.user);
  }, []);

  const register = useCallback(
    async (username: string, displayName: string, password: string) => {
      const response = await api.register(username, displayName, password);
      setUser(response.user);
    },
    []
  );

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
