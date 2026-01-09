/**
 * UserMenu component - Dropdown menu triggered by clicking the user badge.
 * Provides access to Settings, Admin (if admin), and Sign Out.
 */

'use client';

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';

interface UserMenuProps {
  username: string;
  displayName?: string | null;
  isAdmin?: boolean;
  bugReportUrl: string;
  onLogout?: () => void;
  onFeedbackClick: () => void;
}

interface MenuItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  onClick?: () => void;
  href?: string;
  variant?: 'default' | 'danger';
}

export function UserMenu({
  username,
  displayName,
  isAdmin = false,
  bugReportUrl,
  onLogout,
  onFeedbackClick,
}: UserMenuProps) {
  const { t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuItemsRef = useRef<(HTMLAnchorElement | HTMLButtonElement | null)[]>(
    []
  );

  const nameToShow = displayName || username;

  // Build menu items list - memoized to avoid recreating on every render
  const menuItems: MenuItem[] = useMemo(() => {
    const items: MenuItem[] = [
      {
        id: 'feedback',
        label: t.sidebar.sendFeedback || 'Feedback',
        icon: (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5"
          >
            <path
              fillRule="evenodd"
              d="M10 2c-2.236 0-4.43.18-6.57.524C1.993 2.755 1 4.014 1 5.426v5.148c0 1.413.993 2.67 2.43 2.902.848.137 1.705.248 2.57.331v3.443a.75.75 0 001.28.53l3.58-3.579a.78.78 0 01.527-.224 41.202 41.202 0 005.183-.5c1.437-.232 2.43-1.49 2.43-2.903V5.426c0-1.412-.993-2.67-2.43-2.902A41.289 41.289 0 0010 2zm0 7a1 1 0 100-2 1 1 0 000 2zM8 8a1 1 0 11-2 0 1 1 0 012 0zm5 1a1 1 0 100-2 1 1 0 000 2z"
              clipRule="evenodd"
            />
          </svg>
        ),
        onClick: () => {
          setIsOpen(false);
          onFeedbackClick();
        },
      },
      {
        id: 'bug-report',
        label: t.sidebar.reportIssue || 'Report on GitHub',
        icon: (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-5 h-5"
          >
            <path
              fillRule="evenodd"
              d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"
              clipRule="evenodd"
            />
          </svg>
        ),
        href: bugReportUrl,
      },
      {
        id: 'settings',
        label: t.sidebar.settings || 'Settings',
        icon: (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5"
          >
            <path d="M10 3.75a2 2 0 10-4 0 2 2 0 004 0zM17.25 4.5a.75.75 0 000-1.5h-5.5a.75.75 0 000 1.5h5.5zM5 3.75a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5a.75.75 0 01.75.75zM4.25 17a.75.75 0 000-1.5h-1.5a.75.75 0 000 1.5h1.5zM17.25 17a.75.75 0 000-1.5h-5.5a.75.75 0 000 1.5h5.5zM9 10a.75.75 0 01-.75.75h-5.5a.75.75 0 010-1.5h5.5A.75.75 0 019 10zM17.25 10.75a.75.75 0 000-1.5h-1.5a.75.75 0 000 1.5h1.5zM14 10a2 2 0 10-4 0 2 2 0 004 0zM10 16.25a2 2 0 10-4 0 2 2 0 004 0z" />
          </svg>
        ),
        href: '/settings',
      },
    ];

    // Add admin link if user is admin
    if (isAdmin) {
      items.push({
        id: 'admin',
        label: t.sidebar.adminPanel || 'Admin panel',
        icon: (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5"
          >
            <path
              fillRule="evenodd"
              d="M9.661 2.237a.531.531 0 01.678 0 11.947 11.947 0 007.078 2.749.5.5 0 01.479.425c.069.52.104 1.051.104 1.592 0 5.143-3.163 9.537-7.653 11.363a.532.532 0 01-.426 0C5.26 16.537 2.097 12.143 2.097 7.003c0-.54.035-1.07.104-1.592a.5.5 0 01.479-.425 11.947 11.947 0 007.078-2.75z"
              clipRule="evenodd"
            />
          </svg>
        ),
        href: '/admin',
      });
    }

    // Add sign out at the end
    items.push({
      id: 'signout',
      label: t.sidebar.signOut || 'Sign out',
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-5 h-5"
        >
          <path
            fillRule="evenodd"
            d="M3 4.25A2.25 2.25 0 015.25 2h5.5A2.25 2.25 0 0113 4.25v2a.75.75 0 01-1.5 0v-2a.75.75 0 00-.75-.75h-5.5a.75.75 0 00-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 00.75-.75v-2a.75.75 0 011.5 0v2A2.25 2.25 0 0110.75 18h-5.5A2.25 2.25 0 013 15.75V4.25z"
            clipRule="evenodd"
          />
          <path
            fillRule="evenodd"
            d="M19 10a.75.75 0 00-.75-.75H8.704l1.048-.943a.75.75 0 10-1.004-1.114l-2.5 2.25a.75.75 0 000 1.114l2.5 2.25a.75.75 0 101.004-1.114l-1.048-.943h9.546A.75.75 0 0019 10z"
            clipRule="evenodd"
          />
        </svg>
      ),
      onClick: () => {
        setIsOpen(false);
        onLogout?.();
      },
      variant: 'danger',
    });

    return items;
  }, [t, isAdmin, bugReportUrl, onFeedbackClick, onLogout]);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setFocusedIndex(-1);
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () =>
        document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (!isOpen) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          setIsOpen(true);
          setFocusedIndex(0);
        }
        return;
      }

      switch (event.key) {
        case 'Escape':
          event.preventDefault();
          setIsOpen(false);
          setFocusedIndex(-1);
          buttonRef.current?.focus();
          break;
        case 'ArrowDown':
          event.preventDefault();
          setFocusedIndex((prev) => (prev + 1) % menuItems.length);
          break;
        case 'ArrowUp':
          event.preventDefault();
          setFocusedIndex(
            (prev) => (prev - 1 + menuItems.length) % menuItems.length
          );
          break;
        case 'Home':
          event.preventDefault();
          setFocusedIndex(0);
          break;
        case 'End':
          event.preventDefault();
          setFocusedIndex(menuItems.length - 1);
          break;
        case 'Enter':
        case ' ':
          event.preventDefault();
          if (focusedIndex >= 0) {
            const item = menuItems[focusedIndex];
            if (item.onClick) {
              item.onClick();
            } else if (item.href) {
              menuItemsRef.current[focusedIndex]?.click();
            }
          }
          break;
        case 'Tab':
          // Allow tab to move focus naturally but close menu
          setIsOpen(false);
          setFocusedIndex(-1);
          break;
      }
    },
    [isOpen, menuItems, focusedIndex]
  );

  // Focus menu item when focusedIndex changes
  useEffect(() => {
    if (isOpen && focusedIndex >= 0) {
      menuItemsRef.current[focusedIndex]?.focus();
    }
  }, [isOpen, focusedIndex]);

  const toggleMenu = () => {
    setIsOpen((prev) => !prev);
    if (!isOpen) {
      setFocusedIndex(0);
    } else {
      setFocusedIndex(-1);
    }
  };

  return (
    <div className="relative" onKeyDown={handleKeyDown}>
      {/* User badge trigger button */}
      <button
        ref={buttonRef}
        onClick={toggleMenu}
        className="flex items-center gap-2 min-w-0 p-1 -m-1 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-zinc-950"
        aria-expanded={isOpen}
        aria-haspopup="menu"
        data-testid="user-menu-button"
      >
        <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
          <span className="text-white text-sm font-medium">
            {(nameToShow || 'U').charAt(0).toUpperCase()}
          </span>
        </div>
        <span className="text-sm text-zinc-700 dark:text-zinc-300 truncate">
          {nameToShow}
        </span>
        {/* Chevron indicator */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`w-4 h-4 text-zinc-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div
          ref={menuRef}
          role="menu"
          aria-orientation="vertical"
          className="absolute bottom-full left-0 mb-2 w-56 py-1 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-lg shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-50"
          data-testid="user-menu-dropdown"
        >
          {/* User info header */}
          <div className="px-3 py-2 border-b border-zinc-200 dark:border-zinc-700">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
              {nameToShow}
            </p>
            {displayName && displayName !== username && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate">
                @{username}
              </p>
            )}
          </div>

          {/* Menu items */}
          <div className="py-1">
            {menuItems.map((item, index) => {
              const isSignOut = item.id === 'signout';
              const baseClasses =
                'w-full flex items-center gap-3 px-3 py-2 text-sm transition-colors focus:outline-none';
              const colorClasses = isSignOut
                ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 focus:bg-red-50 dark:focus:bg-red-900/20'
                : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 focus:bg-zinc-100 dark:focus:bg-zinc-800';

              // Add separator before sign out
              const showSeparator = isSignOut;

              if (item.href) {
                return (
                  <div key={item.id}>
                    {showSeparator && (
                      <div className="my-1 border-t border-zinc-200 dark:border-zinc-700" />
                    )}
                    <a
                      ref={(el) => {
                        menuItemsRef.current[index] = el;
                      }}
                      href={item.href}
                      target={item.id === 'bug-report' ? '_blank' : undefined}
                      rel={
                        item.id === 'bug-report'
                          ? 'noopener noreferrer'
                          : undefined
                      }
                      className={`${baseClasses} ${colorClasses}`}
                      role="menuitem"
                      tabIndex={focusedIndex === index ? 0 : -1}
                      onClick={() => setIsOpen(false)}
                      data-testid={`user-menu-${item.id}`}
                    >
                      {item.icon}
                      {item.label}
                    </a>
                  </div>
                );
              }

              return (
                <div key={item.id}>
                  {showSeparator && (
                    <div className="my-1 border-t border-zinc-200 dark:border-zinc-700" />
                  )}
                  <button
                    ref={(el) => {
                      menuItemsRef.current[index] = el;
                    }}
                    onClick={item.onClick}
                    className={`${baseClasses} ${colorClasses}`}
                    role="menuitem"
                    tabIndex={focusedIndex === index ? 0 : -1}
                    data-testid={`user-menu-${item.id}`}
                  >
                    {item.icon}
                    {item.label}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
