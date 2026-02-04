# Credit Card Reward Recommendation Engine

## 1) Goal

Build a deterministic engine that recommends which of **3 cards** a user should use for an **upcoming transaction**, based on:

- user preference: `miles` or `cashback`
- monthly progress (caps + thresholds + txn counts)
- transaction attributes (amount, date, channel, overseas)

Outputs: **recommended card + ranked alternatives** with **estimated rewards** and **explanations**.

---

## 2) Wallet (3 Cards)

1. DBS Woman's World Card — Miles (online bonus + monthly cap)
2. UOB PRVI Miles Card — Miles (general earn)
3. UOB One Card — Cashback (monthly tiers + quarterly payout)

---

## 3) Scope

### In scope

- Single user, manual transaction logging
- Calendar-month tracking for cap/tier qualification
- UOB One quarterly payout modeled as **expected monthly value** via `payout/3`
- Deterministic recommendation for one upcoming transaction

### Out of scope (for MVP)

- UOB One category add-ons (partner/grocery/utility)
- Merchant/MCC exclusions and bank “eligible spend” fine print
- Statement-month nuances
- FX fees, installment plans, points posting timelines
- Auto-sync / OCR / bank integration

---

## 4) Inputs & Data Model

### 4.1 Logged Transaction (history)

Required fields:

- `id` (string)
- `date` (YYYY-MM-DD)
- `amount_sgd` (float, >0)
- `card_id` (`ww` | `prvi` | `uobone`)
- `channel` (`online` | `offline`) — needed for WW
- `is_overseas` (bool) *(optional; include only if you model overseas)*

### 4.2 Upcoming Transaction (query)

Same fields except `card_id`.

---

## 5) Card Rule Parameters (Simple MVP)

### 5.1 DBS Woman’s World (id=`ww`, miles)

**Rates**

- `mpd_online = 4.0`
- `mpd_local_base = 0.4`
- OPTIONAL: `mpd_overseas_base = 1.2` (only if `is_overseas=True`)

**Online cap**

- `online_cap_sgd = 1000`
- `cap_period = calendar_month`

**Eligibility**

- Online if `channel == "online"`
- Overseas if `is_overseas == True` (if modeled)

**Counter required**

- `ww_online_spend_used_this_month`

**Spillover rule (must implement)**

If upcoming txn is online and exceeds remaining cap:

- eligible portion earns `mpd_online`
- remainder earns base mpd

**Ignore**

- “DBS points per S$5 block”, posting timelines, exclusions

---

### 5.2 UOB PRVI Miles (id=`prvi`, miles)

**Rates**

- `mpd_local = 1.4`
- OPTIONAL: `mpd_overseas = 3.0` (only if overseas is modeled)

**Caps**

- None

**Ignore**

- “up to 8 mpd hotel/airline bookings”, perks, fees

---

### 5.3 UOB One (id=`uobone`, cashback)

**Qualification gates (monthly)**

- `min_txn_count_per_month = 10`
- `tier_spend_thresholds = [600, 1000, 2000]`

**Quarterly payout by tier**

- `quarterly_payout = {600: 60, 1000: 100, 2000: 200}`
- `payout_period = quarterly`

**MVP scoring uses expected monthly payout**

- `expected_monthly_payout = quarterly_payout[tier] / 3`

**Ignore**

- Additional cashback categories (partner/grocery/utility), fuel, interest, exclusions/caps not shown

---

## 6) Monthly State Computation (from logs)

For month `YYYY-MM` determined by upcoming txn date:

### Per card

- `month_spend_total[card]`
- `month_txn_count[card]`

### Extra for WW

- `ww_online_spend_used = sum(amount_sgd where card=ww AND channel=online)`

---

## 7) Reward Evaluation Functions (per card)

### 7.1 WW miles for upcoming txn

If `txn.channel == online`:

- `remaining = max(0, online_cap_sgd - ww_online_spend_used)`
- `eligible = min(txn.amount_sgd, remaining)`
- `spill = txn.amount_sgd - eligible`
- `mpd_base = mpd_overseas_base if txn.is_overseas else mpd_local_base` *(if overseas modeled)*
- `miles = eligible * mpd_online + spill * mpd_base`
    
    Else:
    
- `mpd_base = ...`
- `miles = txn.amount_sgd * mpd_base`

Rounding: `miles_rounded = round(miles)`.

### 7.2 PRVI miles for upcoming txn

- `mpd = mpd_overseas if overseas else mpd_local` *(if overseas modeled)*
- `miles = txn.amount_sgd * mpd`
    
    Rounding: `round(miles)`.
    

### 7.3 UOB One cashback value for upcoming txn (Simple)

Let:

- `spend_pre = month_spend_total[uobone]`
- `txns_pre = month_txn_count[uobone]`
- `spend_post = spend_pre + txn.amount_sgd`
- `txns_post = txns_pre + 1`

Define `tier(x)` = highest threshold in `[600,1000,2000]` met by spend `x`, else None.

- `tier_pre = tier(spend_pre)`
- `tier_post = tier(spend_post)`

Qualification:

- `qualified_pre = (txns_pre >= 10) AND (tier_pre != None)`
- `qualified_post = (txns_post >= 10) AND (tier_post != None)`

Expected monthly payout:

- `payout_pre = quarterly_payout[tier_pre]/3 if qualified_pre else 0`
- `payout_post = quarterly_payout[tier_post]/3 if qualified_post else 0`

Incremental value of using UOB One for this txn:

- `delta_value = payout_post - payout_pre`

Cashback rounding: `round(delta_value, 2)`.

Explanation must mention:

- progress toward 10 txns
- progress toward next spend tier
- whether txn causes qualification / tier upgrade

---

## 8) Recommendation Policy (Preference + Fallback)

### 8.1 Preference modes

`preference ∈ {miles, cashback}`

### 8.2 Miles preference

- Compute `ww_miles`, `prvi_miles`
- Recommend the larger miles outcome
- Optional fallback to cashback only if:
    - effective miles rate is “low” (configurable), else ignore cashback

Config:

- `MIN_EFFECTIVE_MPD_TO_AVOID_CASHBACK = 1.0`

### 8.3 Cashback preference

- Compute `uobone_delta_value`
- Recommend UOB One if `uobone_delta_value > 0`
- Else fallback to best miles (WW vs PRVI)

---

## 9) Output Contract

Return:

- `recommended_card_id`
- `ranked_cards[]` best→worst, each:
    - `card_id`
    - `reward_unit` (`miles` or `cashback`)
    - `estimated_reward_value`
    - `effective_rate_str`
    - `explanations[]`
- Optional `state_snapshot`: WW cap remaining, UOB One spend/txn progress

---

## 10) Testing (Must-have)

1. WW wins for online txn early month (cap remaining)
2. WW spillover works when txn crosses remaining cap
3. When WW cap exhausted, PRVI wins in miles mode
4. Cashback mode: UOB One txn triggers qualification (10th txn and/or crosses tier) → recommended
5. Cashback mode: UOB One txn does not change qualification → fallback to miles

---

## 11) Deliverables (Engine-only)

- `engine/models.py` — dataclasses/types
- `engine/state.py` — month aggregation
- `engine/cards.py` — evaluators (WW/PRVI/UOB One)
- `engine/recommender.py` — preference + ranking + output formatting
- `tests/` — pytest
- `demo.py` — example run