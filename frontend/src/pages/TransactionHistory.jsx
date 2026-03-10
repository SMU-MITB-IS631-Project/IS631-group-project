import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import CardSurface from '../components/CardSurface';
import { CardThumbnail } from '../components/CardAutocomplete';
import {
  loadCardsMaster,
  loadTransactions,
  loadUserOwnedCards,
  updateTransactionById,
  deleteTransactionById,
} from '../utils/dataAdapter';

function formatDateLabel(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`);
  return d.toLocaleDateString('en-SG', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function toDateInput(dateStr) {
  if (!dateStr) return '';
  return String(dateStr).split('T')[0];
}

export default function TransactionHistory() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');
  const [cardsMaster, setCardsMaster] = useState([]);
  const [ownedCards, setOwnedCards] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({
    item: '',
    amount_sgd: '',
    date: '',
    card_id: '',
    channel: 'online',
    category: '',
    is_overseas: false,
  });

  useEffect(() => {
    async function hydrate() {
      try {
        setIsLoading(true);
        setError('');
        const [txns, cards, walletCards] = await Promise.all([
          loadTransactions({ allowLocalFallback: false, includeDeleted: true }),
          loadCardsMaster(),
          loadUserOwnedCards(),
        ]);
        const filtered = (txns || []).filter(txn => (txn.item || '').trim().toLowerCase() !== 'registration');
        setTransactions(filtered);
        setCardsMaster(cards || []);
        setOwnedCards(walletCards || []);
      } catch (err) {
        setError(err?.message || 'Failed to load transaction history.');
      } finally {
        setIsLoading(false);
      }
    }

    hydrate();
  }, []);

  const cardsById = useMemo(() => {
    const map = new Map();
    cardsMaster.forEach(card => map.set(card.card_id, card));
    return map;
  }, [cardsMaster]);

  const editableCardIds = useMemo(() => {
    const ids = new Set((ownedCards || []).map(card => card.card_id));
    return cardsMaster.filter(card => ids.has(card.card_id));
  }, [ownedCards, cardsMaster]);

  function startEdit(txn) {
    setEditingId(txn.id);
    setForm({
      item: txn.item || '',
      amount_sgd: String(txn.amount_sgd ?? ''),
      date: toDateInput(txn.date),
      card_id: txn.card_id || '',
      channel: txn.channel || 'online',
      category: txn.category || '',
      is_overseas: !!txn.is_overseas,
    });
  }

  function cancelEdit() {
    setEditingId(null);
    setError('');
  }

  async function onSave(transactionId) {
    const parsedAmount = Number(form.amount_sgd);
    if (!form.item.trim() || !form.date || !form.card_id || Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Please fill item, date, card, and a valid amount.');
      return;
    }

    try {
      setIsSaving(true);
      setError('');
      const updated = await updateTransactionById(transactionId, {
        item: form.item.trim(),
        amount_sgd: parsedAmount,
        date: form.date,
        card_id: form.card_id,
        channel: form.channel,
        category: form.category || null,
        is_overseas: form.is_overseas,
      });

      setTransactions(prev => prev.map(txn => (txn.id === transactionId ? updated : txn)));
      setEditingId(null);
    } catch (err) {
      setError(err?.message || 'Failed to update transaction.');
    } finally {
      setIsSaving(false);
    }
  }

  async function onDelete(transactionId) {
    try {
      setError('');
      await deleteTransactionById(transactionId);
      setTransactions(prev => prev.filter(txn => txn.id !== transactionId));
      if (editingId === transactionId) {
        setEditingId(null);
      }
    } catch (err) {
      setError(err?.message || 'Failed to delete transaction.');
    }
  }

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
        <h1 className="text-[20px] font-semibold tracking-tight text-white">Transaction History</h1>
        <span className="w-[42px]" />
      </div>

      {error && (
        <CardSurface className="mb-4 border border-red-300/40">
          <p className="text-sm text-red-600">{error}</p>
        </CardSurface>
      )}

      <CardSurface className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-semibold text-muted uppercase tracking-wide">All Transactions</h2>
          <span className="text-xs text-muted">{transactions.length} records</span>
        </div>
        <p className="text-xs text-muted">View full transaction history. You can update or delete active transactions. Greyed-out transactions can't be edited because the card was deleted.</p>
      </CardSurface>

      <CardSurface>
        {isLoading ? (
          <p className="text-sm text-muted text-center py-6">Loading transaction history...</p>
        ) : transactions.length === 0 ? (
          <p className="text-sm text-muted text-center py-6">No transactions available yet.</p>
        ) : (
          <div className="space-y-3">
            {transactions.map(txn => {
              const isEditing = editingId === txn.id;
              const card = cardsById.get(txn.card_id);
              const status = (txn.status || '').toLowerCase();
              const isDeletedWithCard = status === 'deleted_with_card' || status === 'deletedwithcard';

              return (
                <div
                  key={txn.id}
                  className={`border rounded-[14px] p-3 ${isDeletedWithCard ? 'border-gray-300/80 bg-gray-200/55' : 'border-border/70 bg-white/35'}`}
                >
                  {!isEditing ? (
                    <div>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                          <CardThumbnail imagePath={card?.image_path} name={card?.card_name || txn.card_id} size="sm" />
                          <div className="min-w-0 flex-1">
                            <p className={`text-sm font-semibold break-words ${isDeletedWithCard ? 'text-gray-600' : 'text-text'}`}>{txn.item || 'Unnamed transaction'}</p>
                            <p className={`text-[11px] truncate ${isDeletedWithCard ? 'text-gray-500' : 'text-muted'}`}>{card?.card_name || txn.card_id}</p>
                          </div>
                        </div>
                        <p className={`text-sm font-semibold shrink-0 ${isDeletedWithCard ? 'text-gray-600' : 'text-text'}`}>${Number(txn.amount_sgd).toFixed(2)}</p>
                      </div>

                      <div className="mt-2 flex items-center justify-between">
                        <p className={`text-[11px] ${isDeletedWithCard ? 'text-gray-500' : 'text-muted'}`}>
                          {formatDateLabel(toDateInput(txn.date))} • {txn.channel || 'online'}
                          {isDeletedWithCard ? ' • Deleted with card' : ''}
                        </p>
                        {!isDeletedWithCard && (
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => startEdit(txn)}
                              className="text-xs font-medium text-primary hover:text-primary-dark"
                            >
                              Update
                            </button>
                            <button
                              type="button"
                              onClick={() => onDelete(txn.id)}
                              className="text-xs font-medium text-red-600 hover:text-red-700"
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      <div className="grid grid-cols-2 gap-2">
                        <label className="col-span-2 text-[11px] text-muted">
                          Item
                          <input
                            type="text"
                            value={form.item}
                            onChange={e => setForm(prev => ({ ...prev, item: e.target.value }))}
                            className="mt-1 w-full h-10 px-3 bg-card border border-primary/50 rounded-[10px] text-sm"
                          />
                        </label>
                        <label className="text-[11px] text-muted">
                          Amount (SGD)
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={form.amount_sgd}
                            onChange={e => setForm(prev => ({ ...prev, amount_sgd: e.target.value }))}
                            className="mt-1 w-full h-10 px-3 bg-card border border-primary/50 rounded-[10px] text-sm"
                          />
                        </label>
                        <label className="text-[11px] text-muted">
                          Date
                          <input
                            type="date"
                            value={form.date}
                            onChange={e => setForm(prev => ({ ...prev, date: e.target.value }))}
                            className="mt-1 w-full h-10 px-3 bg-card border border-primary/50 rounded-[10px] text-sm"
                          />
                        </label>
                        <label className="col-span-2 text-[11px] text-muted">
                          Card Used
                          <select
                            value={form.card_id}
                            onChange={e => setForm(prev => ({ ...prev, card_id: e.target.value }))}
                            className="mt-1 w-full h-10 px-3 bg-card border border-primary/50 rounded-[10px] text-sm"
                          >
                            <option value="">Select owned card</option>
                            {editableCardIds.map(ownedCard => (
                              <option key={ownedCard.card_id} value={ownedCard.card_id}>
                                {ownedCard.card_name}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={cancelEdit}
                          className="h-8 px-3 rounded-[10px] border border-border text-xs font-medium"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => onSave(txn.id)}
                          disabled={isSaving}
                          className="h-8 px-3 rounded-[10px] bg-primary text-white text-xs font-medium disabled:opacity-60"
                        >
                          {isSaving ? 'Saving...' : 'Save'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardSurface>
    </div>
  );
}
