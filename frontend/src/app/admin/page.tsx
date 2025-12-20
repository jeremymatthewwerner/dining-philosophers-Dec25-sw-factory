'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { getAdminUsers, deleteUser, updateUserSpendLimit } from '@/lib/api';
import type { UserWithStats } from '@/types';

export default function AdminPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();
  const [users, setUsers] = useState<UserWithStats[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingLimitId, setEditingLimitId] = useState<string | null>(null);
  const [editingLimitValue, setEditingLimitValue] = useState<string>('');

  useEffect(() => {
    if (authLoading) return;

    if (!user) {
      router.push('/login');
      return;
    }

    if (!user.is_admin) {
      router.push('/');
      return;
    }

    loadUsers();
  }, [user, authLoading, router]);

  async function loadUsers() {
    try {
      setIsLoading(true);
      setError(null);
      const data = await getAdminUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDeleteUser(userId: string, username: string) {
    if (
      !confirm(
        `Are you sure you want to delete user "${username}"? This will delete all their conversations and cannot be undone.`
      )
    ) {
      return;
    }

    try {
      setDeletingId(userId);
      await deleteUser(userId);
      setUsers(users.filter((u) => u.id !== userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setDeletingId(null);
    }
  }

  function startEditingLimit(userId: string, currentLimit: number) {
    setEditingLimitId(userId);
    setEditingLimitValue(currentLimit.toString());
  }

  function cancelEditingLimit() {
    setEditingLimitId(null);
    setEditingLimitValue('');
  }

  async function handleUpdateSpendLimit(userId: string) {
    const newLimit = parseFloat(editingLimitValue);
    if (isNaN(newLimit) || newLimit <= 0) {
      setError('Spend limit must be a positive number');
      return;
    }

    try {
      await updateUserSpendLimit(userId, newLimit);
      setUsers(
        users.map((u) =>
          u.id === userId ? { ...u, spend_limit: newLimit } : u
        )
      );
      cancelEditingLimit();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to update spend limit'
      );
    }
  }

  function formatDate(dateString: string) {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }

  function formatCurrency(amount: number) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  }

  if (authLoading || isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-900">
        <div className="text-zinc-500 dark:text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!user?.is_admin) {
    return null;
  }

  const totalSpend = users.reduce((sum, u) => sum + u.total_spend, 0);
  const totalConversations = users.reduce(
    (sum, u) => sum + u.conversation_count,
    0
  );

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <div className="mx-auto max-w-6xl px-4 py-8">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              Admin Panel
            </h1>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              Manage users and view usage statistics
            </p>
          </div>
          <button
            onClick={() => router.push('/')}
            className="rounded-lg bg-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600"
          >
            Back to Chat
          </button>
        </div>

        {/* Stats Cards */}
        <div className="mb-8 grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
            <div className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
              Total Users
            </div>
            <div className="mt-2 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
              {users.length}
            </div>
          </div>
          <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
            <div className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
              Total Conversations
            </div>
            <div className="mt-2 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
              {totalConversations}
            </div>
          </div>
          <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
            <div className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
              Total Spend
            </div>
            <div className="mt-2 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
              {formatCurrency(totalSpend)}
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-4 text-red-700 dark:bg-red-900/20 dark:text-red-400">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-2 font-medium underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Users Table */}
        <div className="overflow-hidden rounded-lg bg-white shadow dark:bg-zinc-800">
          <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              Users
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-zinc-50 dark:bg-zinc-900/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Username
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Role
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Conversations
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Total Spend
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Spend Limit
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Joined
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {users.map((u) => (
                  <tr
                    key={u.id}
                    className="hover:bg-zinc-50 dark:hover:bg-zinc-900/30"
                  >
                    <td className="whitespace-nowrap px-6 py-4">
                      <div className="flex items-center">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                          {u.username.charAt(0).toUpperCase()}
                        </div>
                        <div className="ml-3">
                          <div className="font-medium text-zinc-900 dark:text-zinc-100">
                            {u.username}
                          </div>
                          <div className="text-xs text-zinc-500 dark:text-zinc-400">
                            {u.id.slice(0, 8)}...
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      {u.is_admin ? (
                        <span className="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-800 dark:bg-purple-900/30 dark:text-purple-400">
                          Admin
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-800 dark:bg-zinc-700 dark:text-zinc-300">
                          User
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-zinc-700 dark:text-zinc-300">
                      {u.conversation_count}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-zinc-700 dark:text-zinc-300">
                      {formatCurrency(u.total_spend)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-zinc-700 dark:text-zinc-300">
                      {editingLimitId === u.id ? (
                        <div className="flex items-center gap-2">
                          <span className="text-zinc-500 dark:text-zinc-400">
                            $
                          </span>
                          <input
                            type="number"
                            value={editingLimitValue}
                            onChange={(e) =>
                              setEditingLimitValue(e.target.value)
                            }
                            className="w-20 rounded border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-700"
                            min="0.01"
                            step="0.01"
                            autoFocus
                          />
                          <button
                            onClick={() => handleUpdateSpendLimit(u.id)}
                            className="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300"
                          >
                            Save
                          </button>
                          <button
                            onClick={cancelEditingLimit}
                            className="text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span>{formatCurrency(u.spend_limit)}</span>
                          <button
                            onClick={() =>
                              startEditingLimit(u.id, u.spend_limit)
                            }
                            className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                          >
                            Edit
                          </button>
                        </div>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-zinc-500 dark:text-zinc-400">
                      {formatDate(u.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right">
                      {u.id === user?.id ? (
                        <span className="text-xs text-zinc-400 dark:text-zinc-500">
                          (you)
                        </span>
                      ) : (
                        <button
                          onClick={() => handleDeleteUser(u.id, u.username)}
                          disabled={deletingId === u.id}
                          className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-50"
                          data-testid={`delete-user-${u.id}`}
                        >
                          {deletingId === u.id ? 'Deleting...' : 'Delete'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-6 py-8 text-center text-zinc-500 dark:text-zinc-400"
                    >
                      No users found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
