/**
 * Deterministic mock recommendation engine.
 * getRecommendation({ userProfile, txn, transactions, cardsMaster })
 * Returns: { recommended_card_id, ranked_cards, state_snapshot }
 */
const API_BASE_URL = 'http://localhost:8000';
const USER_ID_KEY = 'cardtrack_user_id';
const CARD_ID_MAP = {
  sc: 1,
  ww: 2,
  prvi: 3,
  uobone: 4,
};

const REVERSE_CARD_ID_MAP = {};
Object.entries(CARD_ID_MAP).forEach(([strId, intId]) => {
  if (!REVERSE_CARD_ID_MAP[intId]) {
    REVERSE_CARD_ID_MAP[intId] = strId;
  }
});

function mapCategoryToBackend(category) {
  const mapping = {
    food: 'Food',
    travel: 'Transport',
    shopping: 'Fashion',
    entertainment: 'Entertainment',
    bills: 'All',
    others: 'All',
  };

  return mapping[category] || 'All';
}

function mapPreferenceToBackend(preference) {
  if (!preference) return 'no_preference';
  const normalized = String(preference).toLowerCase();
  if (normalized === 'miles' || normalized === 'cashback' || normalized === 'points') {
    return normalized;
  }
  return 'no_preference';
}

function convertBackendCardId(backendCardId) {
  if (typeof backendCardId === 'string') {
    if (!isNaN(backendCardId)) {
      backendCardId = parseInt(backendCardId, 10);
    } else {
      return backendCardId;
    }
  }

  const mapped = REVERSE_CARD_ID_MAP[backendCardId];
  if (mapped !== undefined) {
    return mapped;
  }

  return String(backendCardId);
}

function getCurrentUserId(userProfile) {
  const fromStorage = localStorage.getItem(USER_ID_KEY);
  if (fromStorage) return fromStorage;
  if (userProfile?.user_id) return String(userProfile.user_id);
  return null;
}

async function fetchBackendRecommendation({ userProfile, txn }) {
  const userId = getCurrentUserId(userProfile);
  if (!userId) {
    throw new Error('Missing user ID for recommendation API');
  }

  const params = new URLSearchParams({
    user_id: userId,
    amount_sgd: String(parseFloat(txn.amount_sgd) || 0),
    category: mapCategoryToBackend(txn.category),
    preference: mapPreferenceToBackend(userProfile?.preference),
  });

  const response = await fetch(`${API_BASE_URL}/api/v1/recommendation?${params.toString()}`, {
    method: 'GET',
    headers: {
      'x-user-id': userId,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData?.error?.message || 'Failed to fetch recommendations';
    throw new Error(errorMessage);
  }

  return response.json();
}

function normalizeBackendRecommendation(backendResult) {
  const rankedCards = (backendResult?.ranked_cards || []).map(card => ({
    ...card,
    card_id: convertBackendCardId(card.card_id),
    explanations: Array.isArray(card.explanations) ? card.explanations : [],
  }));

  const recommendedCardId = backendResult?.recommended?.card_id ?? rankedCards?.[0]?.card_id ?? null;

  return {
    recommended_card_id: convertBackendCardId(recommendedCardId),
    ranked_cards: rankedCards,
    state_snapshot: {
      target_month: new Date().toISOString().slice(0, 7),
    },
  };
}

export function getRecommendation({ userProfile, txn, transactions, cardsMaster }) {
  const walletCardIds = (userProfile.wallet || []).map(w => w.card_id);
  const preference = userProfile.preference || 'miles';
  const channel = txn.channel || 'online';
  const amount = parseFloat(txn.amount_sgd) || 0;

  // Build card info map
  const cardMap = {};
  cardsMaster.forEach(c => { cardMap[c.card_id] = c; });

  // Determine ranking order
  let ranked = [];

  if (preference === 'miles') {
    if (channel === 'online') {
      // WW first for online miles
      if (walletCardIds.includes('ww')) ranked.push('ww');
      if (walletCardIds.includes('prvi')) ranked.push('prvi');
    } else {
      // PRVI first for offline miles
      if (walletCardIds.includes('prvi')) ranked.push('prvi');
      if (walletCardIds.includes('ww')) ranked.push('ww');
    }
    if (walletCardIds.includes('uobone')) ranked.push('uobone');
  } else {
    // Cashback
    if (walletCardIds.includes('uobone')) ranked.push('uobone');
    if (walletCardIds.includes('ww')) ranked.push('ww');
    if (walletCardIds.includes('prvi')) ranked.push('prvi');
  }

  // Add any remaining wallet cards not yet ranked
  walletCardIds.forEach(cid => {
    if (!ranked.includes(cid)) ranked.push(cid);
  });

  // Build ranked_cards with details
  const rankedCards = ranked.map(cardId => {
    const card = cardMap[cardId];
    const rewardType = card?.reward_type || preference;

    let reward_unit, estimated_reward_value, effective_rate_str, explanations;

    if (cardId === 'ww') {
      reward_unit = 'miles';
      const rate = channel === 'online' ? 4.0 : 1.4;
      estimated_reward_value = Math.round(amount * rate);
      effective_rate_str = `${rate} mpd`;
      explanations = [
        `You prefer ${preference}, and this is ${channel === 'online' ? 'an online' : 'an offline'} transaction.`,
        `DBS WW earns ${rate} mpd on ${channel === 'online' ? 'eligible online spend (up to monthly cap)' : 'offline spend'}.`,
        `Your remaining cap this month supports this transaction.`,
        `Great for accelerating miles on ${channel} purchases.`,
        `No minimum spend requirement for this reward tier.`,
      ];
    } else if (cardId === 'prvi') {
      reward_unit = 'miles';
      const rate = channel === 'offline' ? 2.4 : 1.4;
      estimated_reward_value = Math.round(amount * rate);
      effective_rate_str = `${rate} mpd`;
      explanations = [
        `UOB PRVI earns ${rate} mpd on ${channel} spend.`,
        `Strong earn rate with no quarterly cap for overseas.`,
        `Balanced before-login strategy for miles earners.`,
        `Annual fee waiver available with $50k annual spend.`,
      ];
    } else if (cardId === 'uobone') {
      reward_unit = 'cashback';
      const rate = 3.0;
      estimated_reward_value = (amount * rate / 100).toFixed(2);
      effective_rate_str = `${rate}% cashback`;
      explanations = [
        `UOB One offers up to ${rate}% cashback on qualifying spend.`,
        `Meets your cashback preference with competitive rates.`,
        `Requires min $500/month spend for maximum tier.`,
        `Salary credit to UOB account unlocks best rates.`,
      ];
    } else {
      reward_unit = rewardType;
      estimated_reward_value = Math.round(amount * 1.0);
      effective_rate_str = rewardType === 'miles' ? '1.0 mpd' : '1% cashback';
      explanations = [
        `${card?.card_name || cardId} provides standard rewards.`,
        `Earn rate is baseline for this card type.`,
      ];
    }

    return {
      card_id: cardId,
      reward_unit,
      estimated_reward_value,
      effective_rate_str,
      explanations,
    };
  });

  return {
    recommended_card_id: ranked[0] || null,
    ranked_cards: rankedCards,
    state_snapshot: {
      target_month: new Date().toISOString().slice(0, 7),
    },
  };
}

async function fetchAIExplanation({ userProfile, txn }) {
  const userId = getCurrentUserId(userProfile);
  const payload = {
    amount_sgd: parseFloat(txn.amount_sgd),
    category: mapCategoryToBackend(txn.category),
    merchant_name: txn.item || null,
    preference: mapPreferenceToBackend(userProfile?.preference),
  };

  if (userId) {
    payload.user_id = parseInt(userId, 10);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/recommendation/explain`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(userId ? { 'x-user-id': userId } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData?.error?.message || 'Failed to fetch AI explanation';
    throw new Error(errorMessage);
  }

  return response.json();
}

export async function getRecommendationWithAIExplanation({ userProfile, txn, transactions, cardsMaster }) {
  const backendResult = await fetchBackendRecommendation({ userProfile, txn });
  const baseResult = normalizeBackendRecommendation(backendResult);

  if (!baseResult?.ranked_cards?.length) {
    return baseResult;
  }

  try {
    const aiResponse = await fetchAIExplanation({ userProfile, txn });
    if (!aiResponse?.explanation) {
      return baseResult;
    }

    const rankedCards = baseResult.ranked_cards.map((card, index) => {
      if (index !== 0) {
        return card;
      }

      return {
        ...card,
        ai_explanation: aiResponse.explanation,
        ai_model_used: aiResponse.model_used,
        ai_is_fallback: aiResponse.is_fallback,
        explanations: [aiResponse.explanation, ...card.explanations],
      };
    });

    return {
      ...baseResult,
      ranked_cards: rankedCards,
      ai_explanation: aiResponse.explanation,
      ai_model_used: aiResponse.model_used,
      ai_is_fallback: aiResponse.is_fallback,
    };
  } catch (error) {
    console.warn('[recommendation] AI explanation unavailable, using deterministic reasons:', error.message);
    return baseResult;
  }
}
