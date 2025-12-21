/**
 * Thinker avatar component displaying photo or fallback initials.
 */

'use client';

import Image from 'next/image';
import { useState } from 'react';

export interface ThinkerAvatarProps {
  name: string;
  imageUrl?: string | null;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  color?: string;
}

const SIZE_CLASSES = {
  xs: 'w-4 h-4 text-[8px]',
  sm: 'w-6 h-6 text-xs',
  md: 'w-8 h-8 text-sm',
  lg: 'w-10 h-10 text-base',
};

const SIZE_PIXELS = {
  xs: 16,
  sm: 24,
  md: 32,
  lg: 40,
};

function getInitials(name: string): string {
  const words = name.split(' ').filter(Boolean);
  if (words.length === 0) return '?';
  if (words.length === 1) return words[0].charAt(0).toUpperCase();
  return (words[0].charAt(0) + words[words.length - 1].charAt(0)).toUpperCase();
}

function getColorFromName(name: string): string {
  const colors = [
    '#3B82F6', // blue
    '#10B981', // emerald
    '#F59E0B', // amber
    '#EF4444', // red
    '#8B5CF6', // violet
    '#EC4899', // pink
  ];
  const hash = name
    .split('')
    .reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[hash % colors.length];
}

export function ThinkerAvatar({
  name,
  imageUrl,
  size = 'md',
  color,
}: ThinkerAvatarProps) {
  const [imageError, setImageError] = useState(false);
  const bgColor = color || getColorFromName(name);

  const showImage = imageUrl && !imageError;

  return (
    <div
      className={`relative rounded-full overflow-hidden flex items-center justify-center flex-shrink-0 ${SIZE_CLASSES[size]}`}
      style={!showImage ? { backgroundColor: bgColor } : undefined}
      title={name}
    >
      {showImage ? (
        <Image
          src={imageUrl}
          alt={name}
          width={SIZE_PIXELS[size]}
          height={SIZE_PIXELS[size]}
          className="object-cover w-full h-full"
          onError={() => setImageError(true)}
          unoptimized // Wikipedia images don't need optimization
        />
      ) : (
        <span className="text-white font-medium">{getInitials(name)}</span>
      )}
    </div>
  );
}
