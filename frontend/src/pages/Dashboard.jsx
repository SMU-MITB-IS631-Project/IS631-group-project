import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import CardSurface from '../components/CardSurface';
import { CardThumbnail } from '../components/CardAutocomplete';
import {
  loadCardsMaster, loadUserProfile, loadTransactions,
  getCurrentMonthKey, shiftMonth, formatMonthLabel,
  filterTransactionsByMonth, getMonthSummary, getCardSpendForMonth,
  getAvailableMonths,
} from '../utils/dataAdapter';

function formatDateDMonYYYY(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const day = d.getDate();
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${day}-${months[d.getMonth()]}-${d.getFullYear()}`;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [cardsMaster, setCardsMaster] = useState([]);
  const [profile, setProfile] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [monthKey, setMonthKey] = useState(getCurrentMonthKey());
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  useEffect(() => {
    const p = loadUserProfile();
    if (!p) { navigate('/register'); return; }
    setProfile(p);
    loadCardsMaster().then(setCardsMaster);
  }, []);

  // Reload transactions when returning to this page
  useEffect(() => {
    loadTransactions().then(setTransactions);
  }, []);

  // Also listen for focus to refresh data
  useEffect(() => {
    function handleFocus() {
      loadTransactions().then(setTransactions);
    }
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  const availableMonths = getAvailableMonths(transactions);
  const monthTxns = filterTransactionsByMonth(transactions, monthKey);
  const displayTxns = monthTxns.filter(txn => (txn.item || '').trim().toLowerCase() !== 'registration');
  const summary = getMonthSummary(monthTxns, cardsMaster, profile?.wallet || []);
  const showArrows = availableMonths.length > 1;

  const topCardMaster = cardsMaster.find(c => c.card_id === summary.topCardId);

  function handleConfirmLogout() {
    localStorage.clear();
    setShowLogoutModal(false);
    navigate('/');
  }

  return (
    <div className="pb-6 px-4 pt-6 relative">
      {/* Avatar - Top Left */}
      <div className="absolute top-6 left-6 w-12 h-12 rounded-full overflow-hidden border-2 border-white shadow-lg">
        <img src="https://tse4.mm.bing.net/th/id/OIP.mWxq1EykV6nxFaftjOdFyQHaHa?rs=1&pid=ImgDetMain&o=7&rm=3" alt="Avatar" className="w-full h-full object-cover" />
      </div>

      {/* Logout Button - Top Right */}
      <button
        type="button"
        onClick={() => setShowLogoutModal(true)}
        className="absolute top-6 right-6 w-10 h-10 rounded-full border border-border hover:border-red-400 text-muted hover:text-red-500 font-medium transition-all bg-white hover:bg-red-50 flex items-center justify-center"
        title="Logout"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
          <polyline points="16 17 21 12 16 7"/>
          <line x1="21" y1="12" x2="9" y2="12"/>
        </svg>
      </button>

      {/* Header */}
      <div className="mb-4 px-[14px] pt-20">
        <h1 className="text-[22px] font-semibold tracking-tight text-white">Dashboard</h1>
      </div>

      {/* Logout Confirmation Modal */}
      {showLogoutModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="w-full max-w-[280px] p-6 bg-gradient-to-b from-gray-50 to-gray-100 rounded-[18px] shadow-[0_10px_32px_rgba(0,0,0,0.12),0_0_0_1px_rgba(255,255,255,0.5)]">
            <h2 className="text-lg font-semibold text-primary-dark mb-2">Logout?</h2>
            <p className="text-sm text-muted mb-6">Are you sure you want to logout?</p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowLogoutModal(false)}
                className="flex-1 h-10 border border-border text-text font-medium rounded-lg hover:bg-white/60 transition-all text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmLogout}
                className="flex-1 h-10 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-all text-sm"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Month Selector */}
      <div className="flex items-center justify-center gap-4 mb-5 mt-6">
        {showArrows && (
          <button
            type="button"
            onClick={() => setMonthKey(prev => shiftMonth(prev, -1))}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/60 text-muted transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
          </button>
        )}
        <span className="bg-white px-5 py-1.5 rounded-full text-sm font-semibold text-text shadow-sm border border-border">
          {formatMonthLabel(monthKey)}
        </span>
        {showArrows && (
          <button
            type="button"
            onClick={() => setMonthKey(prev => shiftMonth(prev, 1))}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/60 text-muted transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6"/></svg>
          </button>
        )}
      </div>

      {/* Monthly Summary */}
      <CardSurface className="mb-4">
        <h2 className="text-xs font-semibold text-muted mb-3 uppercase tracking-wide">Monthly Summary</h2>
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <div>
              <div className="text-2xl font-bold text-text">${summary.total.toFixed(2)}</div>
              <div className="text-xs text-muted">Total spend</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-text">{summary.count}</div>
              <div className="text-xs text-muted">Transactions</div>
            </div>
          </div>
          <div className="flex flex-col items-end">
            {topCardMaster && (
              <CardThumbnail imagePath={topCardMaster.image_path} name={topCardMaster.card_name} size="lg" />
            )}
            <div className="mt-2 text-right">
              <div className="text-xs font-medium text-text">Top Card:</div>
              <div className="text-xs text-muted">{summary.topCardSpend > 0 ? summary.topCardName : '—'}</div>
            </div>
          </div>
        </div>
      </CardSurface>

      {/* Transactions List */}
      <CardSurface className="mb-4">
        <h2 className="text-xs font-semibold text-muted mb-3 uppercase tracking-wide">Transactions</h2>

        {displayTxns.length === 0 ? (
          <p className="text-sm text-muted text-center py-4">No transactions yet. Log a transaction from Recommend.</p>
        ) : (
          <div className="divide-y divide-gray-200/60">
            {displayTxns.map(txn => {
              const card = cardsMaster.find(c => c.card_id === txn.card_id);
              return (
                <div key={txn.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-text truncate">{txn.item}</div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium truncate max-w-[120px]">
                        {card?.card_name || txn.card_id}
                      </span>
                      <span className="text-[11px] text-muted">{formatDateDMonYYYY(txn.date)}</span>
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-text ml-3">
                    ${txn.amount_sgd.toFixed(2)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardSurface>

      {/* Card Overview */}
      {profile && profile.wallet && profile.wallet.length > 0 && (
        <CardSurface className="mb-4">
          <h2 className="text-xs font-semibold text-muted mb-3 uppercase tracking-wide">Card Overview</h2>
          <div className="space-y-3">
            {profile.wallet.map(wc => {
              const card = cardsMaster.find(c => c.card_id === wc.card_id);
              const spend = getCardSpendForMonth(monthTxns, wc.card_id);
              return (
                <div key={wc.card_id} className="flex items-center gap-3">
                  <CardThumbnail imagePath={card?.image_path} name={card?.card_name} size="md" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-text truncate">{card?.card_name || wc.card_id}</div>
                    <div className="text-xs text-muted">
                      Annual fee: {wc.annual_fee_billing_date || 'Not set'}
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-text">
                    ${spend.toFixed(2)}
                  </div>
                </div>
              );
            })}
          </div>
        </CardSurface>
      )}
    </div>
  );
}
