import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import CardSurface from '../components/CardSurface';
import SegmentedControl from '../components/SegmentedControl';
import { CardThumbnail } from '../components/CardAutocomplete';
import { loadCardsMaster, loadUserProfile, loadTransactions, appendTransaction } from '../utils/dataAdapter';
import { getRecommendation } from '../utils/recommendation';

export default function Recommend() {
  const navigate = useNavigate();
  const [cardsMaster, setCardsMaster] = useState([]);
  const [profile, setProfile] = useState(null);

  // Transaction form
  const [item, setItem] = useState('');
  const [amount, setAmount] = useState('');
  const [channel, setChannel] = useState('online');

  // Recommendation state
  const [result, setResult] = useState(null);
  const [cursor, setCursor] = useState(0);
  const [exhausted, setExhausted] = useState(false);
  const [selectedFallback, setSelectedFallback] = useState('');
  const [showAllReasons, setShowAllReasons] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    loadCardsMaster().then(setCardsMaster);
    const p = loadUserProfile();
    if (!p) { navigate('/register'); return; }
    setProfile(p);
  }, []);

  async function handleGetRecommendation(e) {
    e.preventDefault();
    if (!item.trim() || !amount) return;

    setIsLoading(true);
    try {
      const txn = { item: item.trim(), amount_sgd: parseFloat(amount), channel, is_overseas: false };
      const transactions = await loadTransactions();
      const rec = getRecommendation({ userProfile: profile, txn, transactions, cardsMaster });
      setResult(rec);
      setCursor(0);
      setExhausted(false);
      setShowAllReasons(false);
      setSelectedFallback('');
    } catch (error) {
      console.error('Error getting recommendation:', error);
      alert('Failed to load transaction history. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }

  function handleNextCard() {
    if (!result) return;
    const nextCursor = cursor + 1;
    if (nextCursor >= result.ranked_cards.length) {
      setExhausted(true);
    } else {
      setCursor(nextCursor);
      setShowAllReasons(false);
    }
  }

  async function handleLog(cardId) {
    setIsLoading(true);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const txn = {
        date: today,
        item: item.trim(),
        amount_sgd: parseFloat(amount),
        card_id: cardId,
        channel,
        is_overseas: false,
      };
      await appendTransaction(txn);
      navigate('/dashboard');
    } catch (error) {
      console.error('Error logging transaction:', error);
      alert('Failed to save transaction. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }

  const currentCard = result && !exhausted ? result.ranked_cards[cursor] : null;
  const currentCardMaster = currentCard ? cardsMaster.find(c => c.card_id === currentCard.card_id) : null;

  return (
    <div className="pb-6 px-4 pt-6">
      {/* Header */}
      <div className="mb-6 px-[14px]">
        <h1 className="text-[22px] font-semibold tracking-tight text-primary-dark">New Transaction</h1>
        <p className="text-sm text-muted mt-1 leading-snug">Enter details to get the best card.</p>
      </div>

      {/* Card A: Transaction Form */}
      <CardSurface className="mb-4">
        <h2 className="text-[15px] font-semibold text-text mb-3">Transaction</h2>
        <form onSubmit={handleGetRecommendation} className="space-y-3">
          <div>
            <label className="text-xs font-medium text-muted mb-1 block">Item</label>
            <input
              type="text"
              value={item}
              onChange={e => setItem(e.target.value)}
              placeholder="GrabFood, Shopee"
              className="w-full h-11 px-3 bg-white border border-border rounded-[14px] text-sm outline-none focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted mb-1 block">Amount (SGD)</label>
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              placeholder="0.00"
              step="0.01"
              min="0"
              className="w-full h-12 px-3 bg-white border border-border rounded-[14px] text-lg font-semibold outline-none focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted mb-1 block">Channel</label>
            <SegmentedControl
              options={[
                { label: 'Online', value: 'online' },
                { label: 'Offline', value: 'offline' },
              ]}
              value={channel}
              onChange={setChannel}
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="w-full h-12 bg-primary hover:bg-primary-dark text-white font-semibold rounded-[14px] transition-colors text-sm mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Loading...' : 'Get Recommendation'}
          </button>
        </form>
      </CardSurface>

      {/* Card B: Recommendation Result */}
      {result && !exhausted && currentCard && (
        <CardSurface className="mb-4">
          <h2 className="text-[15px] font-semibold text-text mb-3">Recommended Card</h2>

          {/* Card info row */}
          <div className="flex items-center gap-3 mb-3">
            <CardThumbnail
              imagePath={currentCardMaster?.image_path}
              name={currentCardMaster?.card_name}
              size="lg"
            />
            <div className="flex-1">
              <div className="font-semibold text-sm text-text">{currentCardMaster?.card_name || currentCard.card_id}</div>
              <div className="text-xs text-muted">{currentCardMaster?.issuer}</div>
            </div>
            <span className="text-xs font-medium text-primary bg-primary/10 px-2 py-1 rounded-full">
              #{cursor + 1} of {result.ranked_cards.length}
            </span>
          </div>

          {/* Chips */}
          <div className="flex gap-2 mb-4 flex-wrap">
            <span className="inline-flex items-center gap-1 text-xs font-medium bg-[#EDE8E1] text-text px-3 py-1.5 rounded-full">
              Est. reward: {currentCard.estimated_reward_value} {currentCard.reward_unit}
            </span>
            <span className="inline-flex items-center gap-1 text-xs font-medium bg-success/10 text-success px-3 py-1.5 rounded-full">
              &#10003; {currentCard.effective_rate_str}
            </span>
          </div>

          {/* Explanations */}
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-muted mb-2">Why this card?</h3>
            <ul className="space-y-1.5">
              {(showAllReasons ? currentCard.explanations : currentCard.explanations.slice(0, 3)).map((exp, i) => (
                <li key={i} className="text-xs text-text flex gap-2">
                  <span className="text-primary mt-0.5 flex-shrink-0">&#8226;</span>
                  <span>{exp}</span>
                </li>
              ))}
            </ul>
            {currentCard.explanations.length > 3 && !showAllReasons && (
              <button
                type="button"
                onClick={() => setShowAllReasons(true)}
                className="text-xs text-primary font-medium mt-2 hover:text-primary-dark"
              >
                Show more
              </button>
            )}
          </div>

          {/* Actions */}
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => handleLog(currentCard.card_id)}
              disabled={isLoading}
              className="w-full h-12 bg-primary hover:bg-primary-dark text-white font-semibold rounded-[14px] transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Logging...' : 'Log this card for transaction'}
            </button>
            <button
              type="button"
              onClick={handleNextCard}
              disabled={isLoading}
              className="w-full h-11 border border-border hover:border-primary text-text font-medium rounded-[14px] transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              I want to select another card
            </button>
          </div>
        </CardSurface>
      )}

      {/* Exhausted State */}
      {result && exhausted && (
        <CardSurface className="mb-4">
          <p className="text-sm text-muted mb-3 text-center">
            No more cards left. Choose one to log.
          </p>
          <div className="space-y-2 mb-4">
            {(profile?.wallet || []).map(wc => {
              const card = cardsMaster.find(c => c.card_id === wc.card_id);
              return (
                <button
                  key={wc.card_id}
                  type="button"
                  onClick={() => setSelectedFallback(wc.card_id)}
                  className={`w-full flex items-center gap-3 p-3 rounded-[14px] border transition-colors text-left ${
                    selectedFallback === wc.card_id
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <CardThumbnail imagePath={card?.image_path} name={card?.card_name} size="md" />
                  <span className="text-sm font-medium text-text">{card?.card_name || wc.card_id}</span>
                </button>
              );
            })}
          </div>
          {selectedFallback && (
            <button
              type="button"
              onClick={() => handleLog(selectedFallback)}
              disabled={isLoading}
              className="w-full h-12 bg-primary hover:bg-primary-dark text-white font-semibold rounded-[14px] transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Logging...' : 'Log selected card'}
            </button>
          )}
        </CardSurface>
      )}
    </div>
  );
}
