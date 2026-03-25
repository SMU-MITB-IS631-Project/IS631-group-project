import React from 'react';

/**
 * CardThumbnail component renders a card image with optional name and size.
 * @param {string} imagePath - The image URL/path for the card.
 * @param {string} name - The alt text or card name.
 * @param {string} size - 'sm' | 'md' | 'lg' (default: 'md')
 */
export default function CardThumbnail({ imagePath, name, size = 'md' }) {
  const sizes = {
    sm: { width: 36, height: 24 },
    md: { width: 60, height: 40 },
    lg: { width: 90, height: 60 },
  };
  const { width, height } = sizes[size] || sizes.md;
  const isStaticLogo = imagePath === '/card-logo.svg';
  return (
    <img
      src={imagePath || '/card-logo.svg'}
      alt={name || 'Card'}
      width={width}
      height={height}
      style={{
        objectFit: 'contain',
        borderRadius: 8,
        background: isStaticLogo ? 'transparent' : '#f3f4f6',
        boxShadow: isStaticLogo ? 'none' : '0 1px 4px rgba(0,0,0,0.04)',
        display: 'block',
      }}
    />
  );
}
