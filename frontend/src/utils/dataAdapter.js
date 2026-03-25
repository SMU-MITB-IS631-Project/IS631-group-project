// --- Monthly Summary ---
/**
 * Aggregates monthly summary for dashboard: total spend, txn count, top card, registration total, etc.
 * @param {Array} transactions - List of transaction objects for the month
 * @param {Array} cardsMaster - List of all card objects (from card catalogue)
 * @param {Array} wallet - User's wallet cards (optional, for baseline spend)
 * @returns {Object} Summary: { total, count, topCardId, topCardName, topCardSpend, registrationTotal }
 */
export function getMonthSummary(transactions, cardsMaster = [], wallet = []) {

  // Get current user id
  const userId = getCurrentUserId && getCurrentUserId();
  // Only include transactions for the logged-in user and not deleted
  const userTxns = (transactions || []).filter(t => {
    const status = (t.status || '').toLowerCase();
    const isDeleted = status === 'deleted_with_card' || status === 'deletedwithcard';
    return String(t.user_id) === String(userId) && !isDeleted;
  });
  // Sum all active transactions for the user, including registration
  const txnTotal = userTxns.reduce((sum, t) => sum + (t.amount_sgd || 0), 0);
  const count = userTxns.length;
  // Registration transaction (monthly salary) for user
  const registrationTotal = userTxns.filter(t => (t.item || '').trim().toLowerCase() === 'registration')
    .reduce((sum, t) => sum + (t.amount_sgd || 0), 0);
  // Baseline: wallet cycle_spend_sgd (not in txns)
  const baselineTotal = (wallet || []).reduce((sum, w) => sum + (parseFloat(w.cycle_spend_sgd) || 0), 0);
  const total = txnTotal + baselineTotal;

  // Top card by spend (txn + baseline)
  const cardSpend = {};
  // Use userTxns for spend calculation (excluding deleted)
  userTxns.forEach(t => {
    cardSpend[t.card_id] = (cardSpend[t.card_id] || 0) + (t.amount_sgd || 0);
  });
  // Add baseline spend from wallet
  (wallet || []).forEach(w => {
    if (w.card_id) {
      cardSpend[w.card_id] = (cardSpend[w.card_id] || 0) + (parseFloat(w.cycle_spend_sgd) || 0);
    }
  });

  let topCardId = null;
  let topSpend = 0;
  Object.entries(cardSpend).forEach(([cid, spend]) => {
    if (spend > topSpend) { topCardId = cid; topSpend = spend; }
  });

  const topCard = (cardsMaster || []).find(c => String(c.card_id) === String(topCardId));

  return {
    total,
    count,
    topCardId,
    topCardName: topCard?.card_name || topCardId,
    topCardSpend: topSpend,
    registrationTotal
  };
}

// Save transactions to localStorage

// Load transactions from localStorage
export function loadTransactionsFromStorage() {
  const raw = localStorage.getItem(TXN_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
import API_BASE_URL from './apiBaseUrl';

const PROFILE_KEY = 'cardtrack_user_profile';
const TXN_KEY = 'cardtrack_transactions';
const USER_ID_KEY = 'cardtrack_user_id';

// --- User Context ---

// Helper to get access token from localStorage
function getAccessToken() {
  return localStorage.getItem('access_token');
}
// TODO: Replace with actual user authentication/context
function getCurrentUserId() {
  return localStorage.getItem(USER_ID_KEY) || '1';
}

function setCurrentUserId(userId) {
  if (userId) {
    localStorage.setItem(USER_ID_KEY, String(userId));
  }
}

// --- User Profile ---

export function loadUserProfile() {
  const raw = localStorage.getItem(PROFILE_KEY);
  if (!raw) {
    return null;
  }
  const profile = JSON.parse(raw);
  if (Array.isArray(profile.wallet)) {
    profile.wallet = profile.wallet.map(card => ({
      ...card,
      card_id: typeof card.card_id === 'string' ? Number(card.card_id) : card.card_id,
    }));
  }
  return profile;
}

export async function loadUserProfileFromAPI() {
  try {
    const userId = getCurrentUserId();
    const accessToken = getAccessToken();
    const response = await fetch(`${API_BASE_URL}/user_profile/user`, {
      method: 'GET',
      headers: {
        'x-user-id': userId,
        'Content-Type': 'application/json',
        ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
      },
    });
    if (!response.ok) {
      throw new Error('Failed to load profile from API');
    }
    const data = await response.json();
    const profile = data;
    try {
      const userId = getCurrentUserId();
      const accessToken = getAccessToken();
      const cardsResponse = await fetch(`${API_BASE_URL}/user/cards/`, {
        method: 'GET',
        headers: {
          'x-user-id': String(userId),
          'Content-Type': 'application/json',
          ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
        },
      });
      if (cardsResponse.ok) {
        const cardsData = await cardsResponse.json();
        profile.wallet = (cardsData.user_cards || cardsData || []).map(card => ({
          ...card,
          card_id: typeof card.card_id === 'string' ? Number(card.card_id) : card.card_id,
        }));
      } else {
        profile.wallet = [];
      }
    } catch (e) {
      profile.wallet = [];
    }
    saveUserProfile(profile);
    return profile;
  } catch (error) {
    console.error('Error loading profile from API:', error);
    return loadUserProfile();
  }
}

export function saveUserProfile(profile) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

async function fetchUserCards(userId) {
  const accessToken = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/user/cards/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
    },
  });
  if (!response.ok) {
    throw new Error('Failed to load user cards');
  }
  const data = await response.json();
  return (data.user_cards || []).map(card => ({
    id: card.id,
    card_id: typeof card.card_id === 'string' ? Number(card.card_id) : card.card_id,
    refresh_day_of_month: card.refresh_day_of_month,
    annual_fee_billing_date: card.annual_fee_billing_date,
  }));
}

export async function loadUserOwnedCards() {
  try {
    const userId = getCurrentUserId();
    return await fetchUserCards(userId);
  } catch (error) {
    console.error('Error loading user owned cards:', error);
    return [];
  }
}



export async function postRegistrationTransactions(userId, walletCards) {
  const accessToken = getAccessToken();
  const payloads = (walletCards || [])
    .filter(w => (w.cycle_spend_sgd || 0) > 0)
    .map(w => ({
      transaction: {
        card_id: typeof w.card_id === 'string' ? Number(w.card_id) : w.card_id,
        amount_sgd: parseFloat(w.cycle_spend_sgd),
        item: 'registration',
        channel: 'online',
        category: 'others',
        is_overseas: false,
        date: new Date().toISOString().split('T')[0],
      },
    }));

  if (payloads.length === 0) {
    return [];
  }

  const responses = await Promise.all(payloads.map(async (payload) => {
    const response = await fetch(`${API_BASE_URL}/api/v1/transactions`, {
      method: 'POST',
      headers: {
        'x-user-id': String(userId),
        'Content-Type': 'application/json',
        ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to create registration transaction: ${response.status} ${errorText}`);
    }

    try {
      const data = await response.json();
      return data?.transaction || null;
    } catch {
      return null;
    }
  }));

  return responses.filter(Boolean);
}

export async function postUserCards(userId, walletCards) {
  const accessToken = getAccessToken();
  const today = new Date().toISOString().split('T')[0];
  const payloads = (walletCards || [])
    .filter(w => w.card_id)
    .map(w => ({
      card_id: Number(w.card_id),
      refresh_day_of_month: parseInt(w.refresh_day_of_month, 10) || 1,
      annual_fee_billing_date: w.annual_fee_billing_date || today,
    }));

  if (payloads.length === 0) {
    return;
  }

  await Promise.all(payloads.map(payload =>
    fetch(`${API_BASE_URL}/user/cards`, {
      method: 'POST',
      headers: {
        'x-user-id': String(userId),
        'Content-Type': 'application/json',
        ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(payload),
    })
  ));
}

/**
 * Register a new user - creates user in backend and saves to localStorage
 */
export async function registerUser(username, password, name, email, preference, wallet) {
  try {
    // Convert preference to proper enum format (capitalize first letter)
    const normalizedPreference = preference 
      ? preference.charAt(0).toUpperCase() + preference.slice(1)
      : 'No preference';
    
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/registration`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username.trim(),
        password,
        name: name || null,
        email: email || null,
        benefits_preference: normalizedPreference,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData?.detail?.error?.message || errorData?.detail || errorData?.error?.message || 'Registration failed');
    }

    const data = await response.json();

    // Seed local profile context so first login/dashboard has wallet/preference metadata.
    const seededProfile = {
      user_id: data.user_id,
      username: username.trim(),
      name: name || username.trim(),
      email: email || null,
      preference: preference || 'miles',
      wallet: Array.isArray(wallet) ? wallet : [],
      created_date: data?.profile?.created_date || new Date().toISOString(),
    };
    saveUserProfile(seededProfile);
    setCurrentUserId(data.user_id);

    // Store wallet info in localStorage for post-login creation
    if (Array.isArray(wallet) && wallet.length > 0) {
      localStorage.setItem('pending_wallet', JSON.stringify(wallet));
    }

    return {
      user_id: data.user_id,
      user_sub: data.user_sub,
      user_confirmed: data.user_confirmed,
      profile: data.profile,
    };
  } catch (error) {
    console.error('Registration error:', error);
    throw error;
  }
}

export async function confirmRegistrationOtp(username, confirmationCode) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/confirmation`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username.trim(),
        confirmation_code: confirmationCode.trim(),
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData?.detail?.error?.message || errorData?.detail || errorData?.error?.message || 'OTP verification failed');
    }

    return await response.json();
  } catch (error) {
    console.error('OTP confirmation error:', error);
    throw error;
  }
}

/**
 * Login with username and password - checks if user exists in the backend
 */
export async function loginUser(username, password) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username.trim(),
        password,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData?.detail?.error?.message || errorData?.detail || errorData?.error?.message || 'Login failed');
    }

    const data = await response.json();
    setCurrentUserId(data.user_id);
    if (data.tokens && data.tokens.access_token) {
      localStorage.setItem('access_token', data.tokens.access_token);
    }
    const existingProfile = loadUserProfile();
    const wallet = existingProfile && existingProfile.username === username.trim()
      ? (existingProfile.wallet || [])
      : [];

    const profile = {
      user_id: data.user_id,
      username: username.trim(),
      name: existingProfile?.name || username.trim(),
      email: existingProfile?.email || null,
      preference: existingProfile?.preference || 'miles',
      wallet,
      created_date: existingProfile?.created_date || new Date().toISOString(),
    };
    saveUserProfile(profile);
    return profile;
  // Helper to get access token from localStorage
  function getAccessToken() {
    return localStorage.getItem('access_token');
  }
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
}

// --- Transactions ---

export async function loadTransactions(options = {}) {
  const { allowLocalFallback = true, includeDeleted = false } = options;
  try {
    const userId = getCurrentUserId();
    const accessToken = getAccessToken();
    const response = await fetch(`${API_BASE_URL}/api/v1/transactions`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
      },
    });
    
    if (!response.ok) {
      throw new Error(`Failed to load transactions: ${response.statusText}`);
    }
    
    const data = await response.json();
    const transactions = data.transactions || [];
    
    const mappedTransactions = transactions.map(txn => ({
      ...txn,
      card_id: typeof txn.card_id === 'string' ? Number(txn.card_id) : txn.card_id
    }));

    const mergedTransactions = mergePendingLocalTransactions(mappedTransactions);
    saveTransactions(mergedTransactions);

    if (includeDeleted) {
      return mergedTransactions;
    }

    // Default behavior for dashboard and existing flows.
    return mergedTransactions.filter(txn => {
      const status = (txn.status || '').toLowerCase();
      return status !== 'deleted_with_card' && status !== 'deletedwithcard';
    });
  } catch (error) {
    console.error('Error loading transactions:', error);
    if (!allowLocalFallback) {
      throw error;
    }
    // Optional fallback for legacy flows; disable when strict server data is required.
    const raw = localStorage.getItem(TXN_KEY);
    return raw ? JSON.parse(raw) : [];
  }
}

export function saveTransactions(txns) {
  localStorage.setItem(TXN_KEY, JSON.stringify(txns));
}


function mergePendingLocalTransactions(serverTransactions) {
  const raw = localStorage.getItem(TXN_KEY);
  if (!raw) {
    return serverTransactions;
  }

  let cachedTransactions = [];
  try {
    cachedTransactions = JSON.parse(raw);
  } catch {
    return serverTransactions;
  }

  const pendingLocalTransactions = (cachedTransactions || []).filter((txn) =>
    typeof txn?.id === 'string' && txn.id.startsWith('local-reg-')
  );

  if (pendingLocalTransactions.length === 0) {
    return serverTransactions;
  }

  const mergedTransactions = [...serverTransactions];
  pendingLocalTransactions.forEach((pendingTxn) => {
    const hasServerMatch = serverTransactions.some((serverTxn) =>
      String(serverTxn.item || '').trim().toLowerCase() === 'registration' &&
      String(pendingTxn.item || '').trim().toLowerCase() === 'registration' &&
      String(serverTxn.card_id) === String(pendingTxn.card_id) &&
      Number(serverTxn.amount_sgd) === Number(pendingTxn.amount_sgd)
    );

    if (!hasServerMatch) {
      mergedTransactions.push(pendingTxn);
    }
  });

  return mergedTransactions;
}

export async function appendTransaction(txn) {
  console.log('[appendTransaction] Called with:', txn);
  try {
    const userId = getCurrentUserId();
    const backendCardId = typeof txn.card_id === 'string' ? Number(txn.card_id) : txn.card_id;
    console.log('[appendTransaction] User ID:', userId);
    console.log('[appendTransaction] Converting card_id:', txn.card_id, '->', backendCardId);
    console.log('[appendTransaction] Sending POST to:', `${API_BASE_URL}/api/v1/transactions`);
    
    const accessToken = getAccessToken();
    const response = await fetch(`${API_BASE_URL}/api/v1/transactions`, {
      method: 'POST',
      headers: {
        'x-user-id': userId,
        'Content-Type': 'application/json',
        ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
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
    
    const createdTransaction = {
      ...data.transaction,
      card_id: typeof data.transaction.card_id === 'string' ? Number(data.transaction.card_id) : data.transaction.card_id,
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

export async function updateTransactionById(transactionId, transactionPatch) {
  const userId = getCurrentUserId();
  const payload = { ...transactionPatch };
  if (payload.card_id !== undefined && payload.card_id !== null) {
    payload.card_id = typeof payload.card_id === 'string' ? Number(payload.card_id) : payload.card_id;
  }
  const accessToken = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/api/v1/transactions/${transactionId}`, {
    method: 'PUT',
    headers: {
      'x-user-id': userId,
      'Content-Type': 'application/json',
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify({ transaction: payload }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update transaction: ${response.statusText}`);
  }
  const data = await response.json();
  return {
    ...data.transaction,
    card_id: typeof data.transaction.card_id === 'string' ? Number(data.transaction.card_id) : data.transaction.card_id,
  };
}

export async function deleteTransactionById(transactionId) {
  const userId = getCurrentUserId();
  const accessToken = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/api/v1/transactions/${transactionId}`, {
    method: 'DELETE',
    headers: {
      'x-user-id': userId,
      ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to delete transaction: ${response.statusText}`);
  }

  try {
    return await response.json();
  } catch {
    return null;
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
  return transactions.filter(t => {
    const status = (t.status || '').toLowerCase();
    const isDeleted = status === 'deleted_with_card' || status === 'deletedwithcard';
    return getMonthKey(t.date) === monthKey && !isDeleted;
  });
}

export function getAvailableMonths(transactions) {
  const keys = new Set(transactions.map(t => getMonthKey(t.date)));
  keys.add(getCurrentMonthKey());
  return Array.from(keys).sort();
}

export function getCardSpendForMonth(transactions, cardId) {
  const txnSpend = transactions
    .filter(t => {
      const status = (t.status || '').toLowerCase();
      const isDeleted = status === 'deleted_with_card' || status === 'deletedwithcard';
      return t.card_id === cardId && !isDeleted;
    })
    .reduce((sum, t) => sum + (t.amount_sgd || 0), 0);
  return txnSpend;
}

// Fetch card catalogue from backend API
export async function loadCardCatalogue() {
  const response = await fetch(`${API_BASE_URL}/api/v1/catalog/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  if (!response.ok) {
    throw new Error('Failed to load card catalogue');
  }
  const data = await response.json();
  return data.cards || data || [];
}

// Utility to convert card ID to number (for compatibility with old imports)
export function convertCardId(cardId) {
  if (typeof cardId === 'number') return cardId;
  if (!isNaN(cardId)) return parseInt(cardId, 10);
  return 1;
}
