import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import CardSurface from '../components/CardSurface';
import CardAutocomplete from '../components/CardAutocomplete';
import SegmentedControl from '../components/SegmentedControl';
import { loadCardsMaster, saveUserProfile } from '../utils/dataAdapter';

const EMPTY_WALLET_CARD = { card_id: '', refresh_day_of_month: 1, annual_fee_billing_date: '', cycle_spend_sgd: '' };

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function getNextRefreshDate(refreshDay) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = parseInt(refreshDay, 10);
  if (!d || d < 1 || d > 31) return null;

  // Advance month until the refresh day is valid in that month and >= today
  let y = today.getFullYear();
  let m = today.getMonth();
  for (let i = 0; i < 13; i++) {
    const candidate = new Date(y, m + i, d);
    // Verify the day didn't overflow to next month (e.g. Feb 30 → Mar 2)
    if (candidate.getDate() === d && candidate >= today) {
      return `${d}-${MONTH_NAMES[candidate.getMonth()]}-${candidate.getFullYear()}`;
    }
  }
  return null;
}

export default function Register() {
  const navigate = useNavigate();
  const [cardsMaster, setCardsMaster] = useState([]);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [walletCards, setWalletCards] = useState([{ ...EMPTY_WALLET_CARD }]);
  const [preference, setPreference] = useState('miles');
  const [errors, setErrors] = useState({});
    // --- prevent duplicate card selection across wallet rows ---
  const takenCardIds = new Set(walletCards.map(w => w.card_id).filter(Boolean));
  function getCardsForRow(rowIndex) {
    const currentId = walletCards[rowIndex]?.card_id;
    return cardsMaster.filter(c => c.card_id === currentId || !takenCardIds.has(c.card_id));
  }

  useEffect(() => {
    loadCardsMaster().then(setCardsMaster);
  }, []);

  function updateWalletCard(index, field, value) {
    setWalletCards(prev => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
    // Clear per-card annual fee error when user fills the date
    if (field === 'annual_fee_billing_date' && value) {
      setErrors(prev => {
        const next = { ...prev };
        delete next[`annualFee_${index}`];
        return next;
      });
    }
  }

  function addWalletCard() {
    setWalletCards(prev => [...prev, { ...EMPTY_WALLET_CARD }]);
  }

  function removeWalletCard(index) {
    if (walletCards.length <= 1) return;
    setWalletCards(prev => prev.filter((_, i) => i !== index));
    // Clear any error for the removed card
    setErrors(prev => {
      const next = { ...prev };
      delete next[`annualFee_${index}`];
      return next;
    });
  }

  function handleSubmit(e) {
    e.preventDefault();
    const newErrors = {};

    if (!username.trim()) newErrors.username = 'Username is required';
    if (!password.trim()) newErrors.password = 'Password is required';
    if (walletCards.every(w => !w.card_id)) newErrors.wallet = 'Add at least one card';

    // Validate annual fee date for each card that has a selected card_id
    walletCards.forEach((wc, idx) => {
      if (wc.card_id && !wc.annual_fee_billing_date) {
        newErrors[`annualFee_${idx}`] = 'Annual fee date is required.';
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const profile = {
      user_id: 'u_001',
      username: username.trim(),
      password: password.trim(),
      preference,
      wallet: walletCards
        .filter(w => w.card_id)
        .map(w => ({ ...w, cycle_spend_sgd: parseFloat(w.cycle_spend_sgd) || 0 })),
    };

    saveUserProfile(profile);
    navigate('/creating');
  }

  return (
    <div className="pb-6 px-4 pt-6">
      {/* Header */}
      <div className="mb-6 px-[14px]">
        <h1 className="text-[22px] font-semibold tracking-tight text-primary-dark">CardTrack</h1>
        <p className="text-sm text-muted mt-1 leading-snug">Track and optimize your credit card rewards</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Account Section */}
        <CardSurface>
          <h2 className="text-[15px] font-semibold text-text mb-3">Account</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted mb-1 block">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="Enter username"
                className="w-full h-11 px-3 bg-white border border-border rounded-[14px] text-sm outline-none focus:border-primary transition-colors"
              />
              {errors.username && <p className="text-red-500 text-xs mt-1">{errors.username}</p>}
            </div>
            <div>
              <label className="text-xs font-medium text-muted mb-1 block">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="w-full h-11 px-3 pr-16 bg-white border border-border rounded-[14px] text-sm outline-none focus:border-primary transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-primary font-medium"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}
            </div>
          </div>
        </CardSurface>

        {/* Wallet Cards Section */}
        <CardSurface>
          <h2 className="text-[15px] font-semibold text-text mb-3">Wallet Cards</h2>
          <div className="space-y-4">
            {walletCards.map((wc, idx) => (
              <div key={idx} className="relative">
                {walletCards.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeWalletCard(idx)}
                    className="absolute -top-1 -right-1 w-5 h-5 bg-muted/20 rounded-full flex items-center justify-center text-muted hover:text-red-500 hover:bg-red-50 text-xs z-10"
                  >
                    &times;
                  </button>
                )}
                <div className="space-y-2.5">
                  <CardAutocomplete
                    cards={getCardsForRow(idx)}
                    value={wc.card_id}
                    onChange={val => updateWalletCard(idx, 'card_id', val)}
                    placeholder="Search for a card..."
                  />
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <label className="text-xs font-medium text-muted mb-1 block">Refresh Date</label>
                      <select
                        value={wc.refresh_day_of_month}
                        onChange={e => updateWalletCard(idx, 'refresh_day_of_month', parseInt(e.target.value))}
                        className="w-full h-11 px-3 bg-white border border-border rounded-[14px] text-sm outline-none focus:border-primary transition-colors appearance-none"
                      >
                        {Array.from({ length: 31 }, (_, i) => i + 1).map(d => (
                          <option key={d} value={d}>{d}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex-1">
                      <label className="text-xs font-medium text-muted mb-1 block">Annual Fee Date</label>
                      <input
                        type="date"
                        value={wc.annual_fee_billing_date}
                        onChange={e => updateWalletCard(idx, 'annual_fee_billing_date', e.target.value)}
                        className={`w-full h-11 px-3 bg-white border rounded-[14px] text-sm outline-none focus:border-primary transition-colors ${
                          errors[`annualFee_${idx}`] ? 'border-red-500' : 'border-border'
                        }`}
                      />
                      {errors[`annualFee_${idx}`] && (
                        <p className="text-red-500 text-xs mt-1">{errors[`annualFee_${idx}`]}</p>
                      )}
                    </div>
                  </div>
                  {wc.refresh_day_of_month && getNextRefreshDate(wc.refresh_day_of_month) && (
                    <p className="text-[11px] text-muted mt-1">
                      Next refresh: {getNextRefreshDate(wc.refresh_day_of_month)}
                    </p>
                  )}
                  <div>
                    <label className="text-xs font-medium text-muted mb-1 block">Spent so far (this cycle)</label>
                    <input
                      type="number"
                      value={wc.cycle_spend_sgd}
                      onChange={e => updateWalletCard(idx, 'cycle_spend_sgd', e.target.value)}
                      placeholder="e.g., 700"
                      step="0.01"
                      min="0"
                      className="w-full h-11 px-3 bg-white border border-border rounded-[14px] text-sm outline-none focus:border-primary transition-colors"
                    />
                  </div>
                </div>
                {idx < walletCards.length - 1 && <hr className="border-border mt-4" />}
              </div>
            ))}
          </div>
          {errors.wallet && <p className="text-red-500 text-xs mt-2">{errors.wallet}</p>}
          <button
            type="button"
            onClick={addWalletCard}
            className="mt-3 text-sm text-primary font-medium hover:text-primary-dark transition-colors"
          >
            + Add another card
          </button>
        </CardSurface>

        {/* Preference Section */}
        <CardSurface>
          <h2 className="text-[15px] font-semibold text-text mb-3">Preference</h2>
          <SegmentedControl
            options={[
              { label: 'Miles', value: 'miles' },
              { label: 'Cashback', value: 'cashback' },
            ]}
            value={preference}
            onChange={setPreference}
          />
          <p className="text-center text-xs text-muted mt-3">You can edit this later.</p>
        </CardSurface>

        {/* Submit */}
        <button
          type="submit"
          className="w-full h-12 bg-primary hover:bg-primary-dark text-white font-semibold rounded-[14px] transition-colors text-sm"
        >
          Create Profile
        </button>
      </form>
    </div>
  );
}
