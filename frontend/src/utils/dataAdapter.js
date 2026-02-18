import { parseCSV } from './csv';

const PROFILE_KEY = 'cardtrack_user_profile';
const TXN_KEY = 'cardtrack_transactions';
const API_BASE_URL = 'http://localhost:8000';

// --- User Context ---
// TODO: Replace with actual user authentication/context
function getCurrentUserId() {
  return '1'; // Hardcoded for now, should come from auth context
}

/**
 * Card ID mapping: Frontend CSV uses string IDs, backend DB uses integers.
 * This mapping converts frontend string IDs to backend integer IDs.
 * 
 * TODO: When the database is properly seeded with actual cards, update this mapping
 * to match the card_catalogue table. For now, all cards map to ID 1 for testing.
 */
const CARD_ID_MAP = {
  'ww': 1,           // DBS Woman's World Card -> Test Card 1 (temporary)
  'prvi': 1,         // UOB PRVI Miles Card -> Test Card 1 (temporary)
  'uobone': 1,       // UOB One Card -> Test Card 1 (temporary)
  'tuvalu': 1,       // Any other cards -> Test Card 1 (temporary)
};

// Reverse mapping: integer -> string (for converting backend responses to frontend format)
const REVERSE_CARD_ID_MAP = {};
Object.entries(CARD_ID_MAP).forEach(([strId, intId]) => {
  if (!REVERSE_CARD_ID_MAP[intId]) {
    REVERSE_CARD_ID_MAP[intId] = strId; // Use first match
  }
});

/**
 * Convert frontend card ID (string) to backend card ID (integer).
 * Falls back to 1 if the card ID is not found in the mapping.
 */
function convertCardId(frontendCardId) {
  // If already a number, return it
  if (typeof frontendCardId === 'number') {
    return frontendCardId;
  }
  
  // If it's a string that looks like a number, parse it
  if (!isNaN(frontendCardId)) {
    return parseInt(frontendCardId);
  }
  
  // Otherwise, look it up in the mapping
  const mapped = CARD_ID_MAP[frontendCardId];
  if (mapped !== undefined) {
    return mapped;
  }
  
  // Fallback to 1 for unknown cards
  console.warn(`Unknown card_id: ${frontendCardId}, falling back to 1`);
  return 1;
}

/**
 * Convert backend card ID (integer) to frontend card ID (string).
 * Falls back to 'ww' if the card ID is not found in the mapping.
 */
function convertBackendCardId(backendCardId) {
  // If already a string, return it
  if (typeof backendCardId === 'string') {
    return backendCardId;
  }
  
  // Look up in reverse mapping
  const mapped = REVERSE_CARD_ID_MAP[backendCardId];
  if (mapped !== undefined) {
    return mapped;
  }
  
  // Fallback to 'ww' for unknown integer IDs
  console.warn(`Unknown backend card_id: ${backendCardId}, falling back to 'ww'`);
  return 'ww';
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

/**
 * Register a new user - creates user in backend and saves to localStorage
 */
export async function registerUser(username, password, name, email, preference, wallet) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/user_profile`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username.trim(),
        password: password.trim(),
        name: name || null,
        email: email || null,
        benefits_preference: preference || 'no preference',
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData?.error?.message || 'Registration failed');
    }

    const data = await response.json();
    
    // Save profile to localStorage for session persistence
    const profile = {
      user_id: data.id,
      username: data.username,
      name: data.name,
      email: data.email,
      preference: data.benefits_preference || 'miles',
      wallet: wallet || [],
      created_date: data.created_date,
    };
    
    saveUserProfile(profile);
    return profile;
  } catch (error) {
    console.error('Registration error:', error);
    throw error;
  }
}

/**
 * Login with username and password - checks if user exists in the backend
 */
export async function loginUser(username, password) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/user_profile/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        username: username.trim(),
        password: password.trim()
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData?.error?.message || 'Login failed');
    }

    const data = await response.json();
    
    const existingProfile = loadUserProfile();
    const existingWallet =
      existingProfile && existingProfile.username === data.username
        ? (existingProfile.wallet || [])
        : [];

    // Save the profile to localStorage for session persistence
    const profile = {
      user_id: data.id,
      username: data.username,
      name: data.name,
      email: data.email,
      preference: data.benefits_preference || 'miles',
      wallet: (data.wallet && data.wallet.length > 0) ? data.wallet : existingWallet,
      created_date: data.created_date,
    };
    
    saveUserProfile(profile);
    return profile;
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
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
    const transactions = data.transactions || [];
    
    // Convert backend integer card_ids to frontend string card_ids
    return transactions.map(txn => ({
      ...txn,
      card_id: convertBackendCardId(txn.card_id)
    }));
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
  console.log('[appendTransaction] Called with:', txn);
  try {
    const userId = getCurrentUserId();
    const backendCardId = convertCardId(txn.card_id);
    console.log('[appendTransaction] User ID:', userId);
    console.log('[appendTransaction] Converting card_id:', txn.card_id, '->', backendCardId);
    console.log('[appendTransaction] Sending POST to:', `${API_BASE_URL}/api/v1/transactions`);
    
    const response = await fetch(`${API_BASE_URL}/api/v1/transactions`, {
      method: 'POST',
      headers: {
        'x-user-id': userId,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        transaction: {
          card_id: backendCardId,
          amount_sgd: parseFloat(txn.amount_sgd),
          item: txn.item,
          channel: txn.channel,
          category: txn.category || null,
          is_overseas: txn.is_overseas || false,
          date: txn.date,
        },
      }),
    });
    
    console.log('[appendTransaction] Response status:', response.status);
    
    if (!response.ok) {
      throw new Error(`Failed to create transaction: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('[appendTransaction] Success! Created transaction:', data.transaction);
    
    // Convert backend integer card_id back to frontend string card_id
    const createdTransaction = {
      ...data.transaction,
      card_id: convertBackendCardId(data.transaction.card_id)
    };
    
    return createdTransaction;
  } catch (error) {
    console.error('[appendTransaction] Error creating transaction:', error);
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
