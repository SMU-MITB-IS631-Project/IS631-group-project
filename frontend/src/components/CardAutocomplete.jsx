import { useState, useRef, useEffect } from 'react';
import VerifiedBadge from './VerifiedBadge';

export default function CardAutocomplete({ cards, value, onChange, placeholder = 'Search card...' }) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef(null);

  const selectedCard = cards.find(c => c.card_id === value);
  const isVerified = !!selectedCard;

  const filtered = cards.filter(c =>
    c.card_name.toLowerCase().includes(query.toLowerCase()) ||
    c.card_id.toLowerCase().includes(query.toLowerCase()) ||
    c.issuer.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (selectedCard && !query) {
      setQuery(selectedCard.card_name);
    }
  }, [value]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={query}
            placeholder={placeholder}
            onChange={e => {
              setQuery(e.target.value);
              setIsOpen(true);
              if (!e.target.value) onChange('');
            }}
            onFocus={() => setIsOpen(true)}
            className="w-full h-11 px-3 pr-10 bg-white border border-border rounded-[14px] text-sm outline-none focus:border-primary transition-colors"
          />
          {isVerified && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2">
              <VerifiedBadge />
            </span>
          )}
        </div>
      </div>

      {isOpen && filtered.length > 0 && (
        <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-white border border-border rounded-[14px] shadow-lg max-h-48 overflow-y-auto">
          {filtered.map(card => (
            <button
              key={card.card_id}
              type="button"
              onClick={() => {
                onChange(card.card_id);
                setQuery(card.card_name);
                setIsOpen(false);
              }}
              className="w-full text-left px-3 py-2.5 hover:bg-bg text-sm flex items-center gap-2 transition-colors first:rounded-t-[14px] last:rounded-b-[14px]"
            >
              <CardThumbnail imagePath={card.image_path} name={card.card_name} size="sm" />
              <div>
                <div className="font-medium text-text">{card.card_name}</div>
                <div className="text-xs text-muted">{card.issuer}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function CardThumbnail({ imagePath, name, size = 'md' }) {
  const sizes = {
    sm: 'w-8 h-5',
    md: 'w-12 h-8',
    lg: 'w-16 h-10',
  };

  return (
    <div className={`${sizes[size]} rounded bg-gradient-to-br from-primary/20 to-primary/40 flex items-center justify-center overflow-hidden flex-shrink-0`}>
      <img
        src={imagePath}
        alt={name}
        className="w-full h-full object-cover"
        onError={e => {
          e.target.style.display = 'none';
          e.target.parentElement.innerHTML = `<span class="text-[8px] text-primary font-medium text-center leading-tight px-0.5">${name?.split(' ').slice(0, 2).join(' ') || 'Card'}</span>`;
        }}
      />
    </div>
  );
}
