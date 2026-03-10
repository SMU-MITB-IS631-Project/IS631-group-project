import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import CardSurface from '../components/CardSurface';
import { CardThumbnail } from '../components/CardAutocomplete';
import {
  convertCardId,
  filterTransactionsByMonth,
  getCurrentMonthKey,
  loadCardsMaster,
  loadTransactions,
  loadUserProfile,
} from '../utils/dataAdapter';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function formatRate(benefitType, rate) {
  if (rate === null || rate === undefined || Number.isNaN(Number(rate))) {
    return '-';
  }
  const numericRate = Number(rate);
  if ((benefitType || '').toLowerCase().includes('cash')) {
    const percent = numericRate > 1 ? numericRate : numericRate * 100;
    return `${percent.toFixed(2)}% cashback`;
  }
  return `${numericRate.toFixed(2)} mpd`;
}

export default function CardBonusDescription() {
  const navigate = useNavigate();
  const { cardId } = useParams();
  const [cardsMaster, setCardsMaster] = useState([]);
  const [catalogCard, setCatalogCard] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const profile = loadUserProfile();

  useEffect(() => {
    let cancelled = false;

    async function loadCardBonusData() {
      try {
        setLoading(true);
        setLoadError('');

        const backendCardId = convertCardId(cardId);

        const [cardsMasterData, catalogRes, transactionsData] = await Promise.all([
          loadCardsMaster(),
          fetch(`${API_BASE_URL}/api/v1/catalog/`),
          loadTransactions(),
        ]);

        if (cancelled) return;
        setCardsMaster(cardsMasterData);
        setTransactions(transactionsData || []);

        if (!catalogRes.ok) {
          throw new Error('Failed to load card catalogue data');
        }
        const catalogData = await catalogRes.json();
        const matchedCatalogCard = (catalogData || []).find((card) => card.card_id === backendCardId) || null;
        setCatalogCard(matchedCatalogCard);
      } catch (error) {
        if (cancelled) return;
        console.error('Failed to load card bonus data:', error);
        setLoadError('Unable to load live card details from backend.');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadCardBonusData();

    return () => {
      cancelled = true;
    };
  }, [cardId]);

  const backendCardIdFromRoute = useMemo(() => convertCardId(cardId), [cardId]);

  const selectedCard = useMemo(
    () => cardsMaster.find((card) => card.card_id === cardId || convertCardId(card.card_id) === backendCardIdFromRoute),
    [cardsMaster, cardId, backendCardIdFromRoute]
  );

  const walletCard = useMemo(
    () => (profile?.wallet || []).find((card) => card.card_id === cardId || convertCardId(card.card_id) === backendCardIdFromRoute),
    [profile, cardId, backendCardIdFromRoute]
  );

  const displayCardName = catalogCard?.card_name || selectedCard?.card_name || cardId;
  const displayIssuer = catalogCard?.bank || selectedCard?.issuer || '-';
  const displayBenefitType = catalogCard?.benefit_type || selectedCard?.reward_type || '-';
  const baseRateText = formatRate(displayBenefitType, catalogCard?.base_benefit_rate);

  const thisMonthSpend = useMemo(() => {
    const currentMonthTransactions = filterTransactionsByMonth(transactions, getCurrentMonthKey());
    return currentMonthTransactions
      .filter((txn) => convertCardId(txn.card_id) === backendCardIdFromRoute)
      .reduce((sum, txn) => sum + (Number(txn.amount_sgd) || 0), 0);
  }, [transactions, backendCardIdFromRoute]);

  const expectedRewards = useMemo(() => {
    if (!catalogCard) {
      return null;
    }
    const baseRate = Number(catalogCard.base_benefit_rate);
    if (Number.isNaN(baseRate)) {
      return null;
    }

    const rewardAmount = thisMonthSpend * baseRate;
    const benefitTypeLower = (displayBenefitType || '').toLowerCase();
    const isCashback = benefitTypeLower.includes('cash');
    return {
      value: Number(rewardAmount),
      isCashback,
      formatted: isCashback ? `$${Number(rewardAmount).toFixed(2)}` : `${Math.round(Number(rewardAmount))} miles`,
    };
  }, [catalogCard, displayBenefitType, thisMonthSpend]);

  return (
    <div className="px-4 pt-6 pb-10">
      <div className="mb-4 px-[6px] pt-2 flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="text-sm text-white/85 hover:text-white transition-colors"
        >
          ← Back
        </button>
        <h1 className="text-[20px] font-semibold tracking-tight text-white">Card Bonus</h1>
        <span className="w-[42px]" />
      </div>

      {loading ? (
        <CardSurface>
          <p className="text-sm text-muted text-center py-6">Loading card bonus details...</p>
        </CardSurface>
      ) : !selectedCard && !catalogCard ? (
        <CardSurface>
          <p className="text-sm text-muted text-center py-6">Card not found. Please return to Dashboard and select a card again.</p>
        </CardSurface>
      ) : (
        <>
          <CardSurface className="mb-4">
            <div className="flex items-center gap-3">
              <CardThumbnail imagePath={selectedCard?.image_path} name={displayCardName} size="lg" />
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-text truncate">{displayCardName}</h2>
                <p className="text-xs text-muted mt-0.5">{displayIssuer} • {displayBenefitType}</p>
              </div>
            </div>
          </CardSurface>

          <CardSurface className="mb-4">
            {loadError ? (
              <p className="text-sm text-amber-700">{loadError}</p>
            ) : (
              <div className="space-y-3">
                <div className="rounded-xl border border-border/70 px-4 py-4 bg-white/45">
                  <p className="text-xs text-muted mb-1">Total spent this month on this card</p>
                  <p className="text-2xl font-semibold text-text tabular-nums">${thisMonthSpend.toFixed(2)}</p>
                </div>
                {expectedRewards && (
                  <div className="rounded-xl border border-border/70 px-4 py-4 bg-white/45">
                    <p className="text-xs text-muted mb-1">Total rewards to be earned on this card this month</p>
                    <p className="text-2xl font-semibold text-text tabular-nums">{expectedRewards.formatted}</p>
                  </div>
                )}
              </div>
            )}
          </CardSurface>

          <CardSurface>
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Card Info</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted">Base benefit rate</span>
                <span className="font-medium text-text">{baseRateText}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted">Refresh day</span>
                <span className="font-medium text-text">{walletCard?.refresh_day_of_month || 'Not set'}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted">Annual fee date</span>
                <span className="font-medium text-text">{walletCard?.annual_fee_billing_date || 'Not set'}</span>
              </div>
            </div>
          </CardSurface>
        </>
      )}
    </div>
  );
}
