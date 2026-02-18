import { parseCSV } from './csv';

const PROFILE_KEY = 'cardtrack_user_profile';
const TXN_KEY = 'cardtrack_transactions';
const API_BASE_URL = 'http://localhost:8000';

// --- User Context ---
// TODO: Replace with actual user authentication/context
function getCurrentUserId() {
  return '1'; // Hardcoded for now, should come from auth context
}

// --- CSV Loader ---

export async function loadCardsMaster() {
  const res = await fetch('/data/cards_master.csv');
  const text = await res.text();
  return parseCSV(text);
}

// --- User Profile ---

export function loadUserProfile() {
  const raw = localStorage.getItem(PROFILE_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function saveUserProfile(profile) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

// --- Transactions ---

export async function loadTransactions() {
  try {
    const userId = getCurrentUserId();
    const response = await fetch(`${API_BASE_URL}/api/v1/transactions`, {
      method: 'GET',
      headers: {
        'x-user-id': userId,
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error(`Failed to load transactions: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.transactions || [];
  } catch (error) {
    console.error('Error loading transactions:', error);
    // Fallback to localStorage if API fails
    const raw = localStorage.getItem(TXN_KEY);
    return raw ? JSON.parse(raw) : [];
  }
}

export function saveTransactions(txns) {
  localStorage.setItem(TXN_KEY, JSON.stringify(txns));
}

export async function appendTransaction(txn) {
  try {
    const userId = getCurrentUserId();
    const response = await fetch(`${API_BASE_URL}/api/v1/transactions`, {
      method: 'POST',
      headers: {
        'x-user-id': userId,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        transaction: {
          card_id: parseInt(txn.card_id),
          amount_sgd: parseFloat(txn.amount_sgd),
          item: txn.item,
          channel: txn.channel,
          category: txn.category || null,
          is_overseas: txn.is_overseas || false,
          date: txn.date,
        },
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to create transaction: ${response.statusText}`);
    }
    
    const data = await response.json();
    // Return the newly created transaction
    return data.transaction;
  } catch (error) {
    console.error('Error creating transaction:', error);
    // Fallback to localStorage if API fails
    const txns = await loadTransactions();
    txns.push(txn);
    saveTransactions(txns);
    return txn;
  }
}

// --- Month Utilities ---

export function getMonthKey(date) {
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export function formatMonthLabel(monthKey) {
  const [y, m] = monthKey.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[parseInt(m, 10) - 1]} ${y}`;
}

export function getCurrentMonthKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export function shiftMonth(monthKey, delta) {
  const [y, m] = monthKey.split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export function filterTransactionsByMonth(transactions, monthKey) {
  return transactions.filter(t => getMonthKey(t.date) === monthKey);
}

export function getMonthSummary(transactions, cardsMaster, wallet = []) {
  const txnTotal = transactions.reduce((sum, t) => sum + (t.amount_sgd || 0), 0);
  const baselineTotal = wallet.reduce((sum, wc) => sum + (wc.cycle_spend_sgd || 0), 0);
  const total = txnTotal + baselineTotal;
  const count = transactions.length;

  // Top card by spend (txn spend + baseline per card)
  const cardSpend = {};
  wallet.forEach(wc => {
    cardSpend[wc.card_id] = (cardSpend[wc.card_id] || 0) + (wc.cycle_spend_sgd || 0);
  });
  transactions.forEach(t => {
    cardSpend[t.card_id] = (cardSpend[t.card_id] || 0) + (t.amount_sgd || 0);
  });

  let topCardId = null;
  let topSpend = 0;
  Object.entries(cardSpend).forEach(([cid, spend]) => {
    if (spend > topSpend) { topCardId = cid; topSpend = spend; }
  });

  const topCard = cardsMaster.find(c => c.card_id === topCardId);

  return { total, count, topCardId, topCardName: topCard?.card_name || topCardId, topCardSpend: topSpend };
}

export function getAvailableMonths(transactions) {
  const keys = new Set(transactions.map(t => getMonthKey(t.date)));
  keys.add(getCurrentMonthKey());
  return Array.from(keys).sort();
}

export function getCardSpendForMonth(transactions, cardId, cycleSpend = 0) {
  const txnSpend = transactions
    .filter(t => t.card_id === cardId)
    .reduce((sum, t) => sum + (t.amount_sgd || 0), 0);
  return txnSpend + cycleSpend;
}
