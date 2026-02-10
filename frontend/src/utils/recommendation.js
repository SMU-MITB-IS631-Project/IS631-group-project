/**
 * Deterministic mock recommendation engine.
 * getRecommendation({ userProfile, txn, transactions, cardsMaster })
 * Returns: { recommended_card_id, ranked_cards, state_snapshot }
 */
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
