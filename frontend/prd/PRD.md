# CardTrack — PRD v1.1 (Final, Single File)

**Project:** CardTrack (Credit Card Recommendation UI Prototype)  
**Mode:** UI-only, CSV-seeded (read-only), LocalStorage persistence (read/write)  
**Pages:** 3 main screens (Register, Recommend, Dashboard) + 1 transient loading route (`/creating`)  
**Goal:** Deliver a polished mobile-first UI with interactive recommendation loop and dashboard updates, matching the provided UI mock.

---

## 1) Product Requirements

### 1.1 Objective

Build a mobile UI prototype that lets users:
1. Register and set up wallet cards
2. Enter a transaction and receive ranked card recommendations with explanations
3. Log the transaction and view an updated dashboard (transactions + card overview)

### 1.2 Scope

#### In scope

- 3 screens + bottom navigation (conditional rendering based on profile existence)
- Card autocomplete + verified badge/tick (SVG asset)
- Wallet setup supports multiple cards
- Wallet setup captures **cycle spend baseline per card** ("Spent so far (this cycle)")
- Refresh UX helper:
  - Show "Next refresh: …" computed from refresh day-of-month + today's date (robust for invalid days like Feb 30)
- Post-profile creation loading transition:
  - `/creating` loading page shown briefly after Create Profile
- Recommendation loop:
  - show top recommended card with explanation
  - "Next best card" cycles ranked list
  - "Log this card" persists txn
  - exhausted state when no more ranked cards
- Dashboard:
  - Available months derived from logged transactions
  - If **no logged transactions exist**, available months defaults to **[current month only]**
  - Monthly summary totals based on:
    - **logged transactions + baseline spend**
    - **txn count based on logged transactions only**
  - Transaction list (logged transactions only)
  - Prior Spend section shown above transactions (display-only baseline rows; not transactions)
  - Card overview (current month spend includes baseline + logged txns; annual fee date per card)
  - Empty-state message when no logged transactions
  - Month arrows are **conditionally shown** (only when there are multiple months)
- Mobile frame scroll UX:
  - inner content scrollable with **hidden scrollbar** (phone-like)
- Dashboard UI polish:
  - "Top Card" positioning aligned to right thumbnail area
  - Transaction list faint dividers between rows
  - Strong divider after Prior Spend section, before Transactions list
  - Transaction dates formatted as `D-MMM-YYYY` (e.g., `3-Mar-2026`)

#### Out of scope

- Real authentication/security
- Real DB/API integration
- Payment/MCC/FX nuance beyond prototype
- Any server write access (LocalStorage only)
- Demo/seeded transactions (prototype must not auto-create transactions)

### 1.3 User Flows

#### First-time user

1. Launch → `/register`
2. Fill profile + wallet cards → Create Profile
3. Navigate to `/creating` (loading)
4. Auto-redirect → `/dashboard` (default)
5. Tap Recommend → `/recommend` → Get recommendation → Log → returns to `/dashboard`

#### Returning user

- Launch → `/dashboard`

### 1.4 Acceptance Criteria

- User can create profile and add 1+ cards
- Card field provides suggestions from seeded master list
- Verified badge appears only when selected card exists in master list
- Verified badge uses SVG tick asset: `/assets/cards/tick.svg`
- Register screen header:
  - **No "Step 1 of 3: Create Profile" pill** on the Register screen
- Each wallet card captures:
  - refresh day-of-month (1–31) (label: "Refresh")
  - annual fee date (required if card is selected)
  - spent so far (this cycle) = `cycle_spend_sgd`
- Register validation:
  - If a wallet card has a selected `card_id`, then `annual_fee_billing_date` is **required**
  - On Create Profile, missing annual fee date shows inline red error under that field and prevents save/navigation
- Register helper text:
  - "Next refresh: …" is computed robustly:
    - If chosen day does not exist in the current month (e.g., Feb 30), the next refresh rolls forward to the next month where it is valid (e.g., 30 Mar 2026)
- Create Profile flow:
  - Validates required fields
  - Saves profile to LocalStorage
  - Navigates to `/creating` (loading screen)
  - Redirects to `/dashboard` after ~800ms (acceptable range 600–1200ms)
- Recommendation returns ranked list; UI cycles with cursor
- Logging transaction updates dashboard totals and lists immediately
- New user dashboard behavior:
  - Available months defaults to **current month only** when no transactions exist
  - Total spend reflects **baseline_total + txn_total**
  - Transaction count reflects **logged transactions only**
  - Prior Spend section shown if any `cycle_spend_sgd > 0` even if there are 0 transactions
- Dashboard month selector:
  - If only one month is available → **no left/right arrows**
- Dashboard transaction date format:
  - Render as **`D-MMM-YYYY`** (day no leading zero; short month; 4-digit year)
- UI matches the mock: clean, card-based, warm background, muted purple primary
- UI renders in a **mobile phone frame** on desktop (centered, 375–390px width) with **hidden scrollbar UI**

---

## 2) UI Spec (Figma-lite)

### 2.1 Layout & Visual Style (Design Tokens)

**Baseline viewport:** 375 × 812 (mobile)

**Colors**

- `bg`: #F3EDE6 (warm beige)
- `card`: #FFFFFF (or #FFFDFB)
- `primary`: #5B556B (muted purple)
- `primaryDark`: #4A445B
- `text`: #1F1F1F
- `muted`: #6B7280
- `border`: #E5E7EB
- `success`: #16A34A (verified)
- `shadow`: subtle (e.g., 0 8px 24px rgba(0,0,0,0.08))

**Typography**

- App title: 22–24px, semibold
- Page title: 18–20px, semibold
- Section heading: 14–16px, medium
- Body: 13–14px
- Caption: 12px

**Spacing**

- Screen padding: 16px
- Card padding: 16px
- Vertical gaps: 12–16px
- Input height: 44px
- Button height: 48px

**Radius**

- Main cards: 18px
- Inputs/buttons: 14px
- Chips/badges: 999px

**Background**

- Use a subtle pattern image at very low opacity (5–10%)
- Pattern is applied **inside the device frame only** (not full browser body)
- Content sits in a primary "surface card" with gentle shadow

### 2.2 Navigation

**Routes**

- `/register`
- `/creating`
- `/recommend`
- `/dashboard`

**Bottom nav (conditional)**

- If `cardtrack_user_profile` does **not** exist:
  - show **Profile** → `/register` only
  - **do not show Dashboard**
- If `cardtrack_user_profile` exists:
  - show **Recommend** → `/recommend`
  - show **Dashboard** → `/dashboard`
  - **Profile tab disappears**

**Default routing**

- If `cardtrack_user_profile` exists in LocalStorage → `/dashboard`
- Else → `/register`

**Routing guard**

- If no profile exists, any route redirects to `/register`
- If `/creating` is accessed without a profile, redirect to `/register`

### 2.3 Mobile Frame Rendering (Desktop Preview)

Render inside a centered "device frame" to mimic a phone:

- width: 375–390px, centered (`mx-auto`)
- height: `min(812px, 92vh)`
- rounded corners + subtle border + shadow
- `overflow-hidden`
- inner content scrollable
- **scrollbar UI hidden** (no visible scrollbar, phone-like)
- Bottom nav fixed at bottom **inside the frame**
- background pattern should be inside the frame (not full browser width)

---

## 3) Screen Specifications

### Screen 1: Registration (`/register`)

**Header**

- App name: "CardTrack"
- Subtitle: "Track and optimize your credit card rewards"
- **No step pill**: do not show "Step 1 of 3: Create Profile"

**Sections**

#### 1. Account
- Username (text)
- Password (password) + "Show" toggle

#### 2. Wallet Cards
- List of wallet card blocks (repeatable)
- Each wallet card block:
  - Card selector with autocomplete (from `cards_master.csv`)
    - right side: Verified badge shown only when valid
    - tick asset: `src="/assets/cards/tick.svg"`
  - Row of 2 fields:
    - Refresh Day (dropdown 1–31, label: "Refresh")
    - Annual Fee Date (date input)
  - Helper text (muted):
    - "Next refresh: DD MMM YYYY" (computed robustly from refresh day + today)
  - Full-width field:
    - **Spent so far (this cycle)** (number, SGD, default 0)
    - helper: "Amount already spent since last refresh date."
- Secondary action: "+ Add another card"

**Annual Fee Date validation**
- If a wallet card block has a selected `card_id`, then Annual Fee Date is required
- On Create Profile:
  - show inline error text under the date input (red), e.g. "Annual fee date is required."
  - prevent save/navigation until resolved
  - (optional) highlight date input border in red

**Next refresh computation (robust)**
- Uses today's device date (local timezone)
- If `refresh_day_of_month` is invalid for the current month, roll forward month-by-month until a valid date exists
- If the candidate date in the current month is earlier than today, roll forward to the next valid month

#### 3. Preference
- Segmented control: Miles | Cashback
- Helper text (inside the Preference card, below segmented control):
  - "You can edit this later."

**Footer**

- Primary CTA: "Create Profile" (full width)

**Create Profile action**

- Validate required fields
- Save profile + wallet to LocalStorage
- Navigate to `/creating`

---

### Screen 1.5: Creating (`/creating`) — Loading Screen (transient)

**Purpose**
A short "initializing" screen shown after Create Profile to bridge setup → main app.

**UI**
- Title: "Setting up your wallet…"
- Subtitle: "Preparing your dashboard and recommendations"
- Spinner or subtle animated dots

**Behavior**
- If profile missing → redirect to `/register`
- Else show loading for ~800ms (range 600–1200ms acceptable)
- Then redirect to `/dashboard`
- Bottom nav may be hidden or disabled on this screen

---

### Screen 2: Recommend (`/recommend`)

**Header**

- Title: "New Transaction"
- Subtitle: "Enter details to get the best card."

**Card A: Transaction**

- Item (text, placeholder "GrabFood, Shopee")
- Amount (number, large emphasis)
- Channel segmented control: Online | Offline
- Primary button: "Get Recommendation"

**Card B: Recommended Card (appears after recommendation computed)**

- Title: "Recommended Card"
- Card row: thumbnail + card name + rank indicator (e.g., "#1 of 3")
- Chips row:
  - Est. reward (e.g., "Est. reward: 400 miles")
  - Effective rate (e.g., "✓ 4.0 mpd")
- Reasoning:
  - Heading: "Why this card?"
  - Bullet list: show up to 3 bullets initially
  - "Show more" expands full list

**Actions**

- Primary: "Log this card for transaction"
- Secondary: "I want to select another card"

**Exhausted state**
If user clicks next and no more ranked cards:

- Show info line: "No more cards left. Choose one to log."
- Render a list of wallet cards as selectable rows (tap to select), then show "Log selected card".

**Logging action**

- Append txn (with chosen card_id) to LocalStorage transactions
- Navigate to `/dashboard`

---

### Screen 3: Dashboard (`/dashboard`)

**Header**

- Title: "Dashboard"
- Month pill shows current selected month
- Arrows only show if multiple months exist
- If no txns exist → month list defaults to [current month only]

#### Baseline spend rule (global)
- Baseline is **not a transaction**
- Baseline **does contribute to spend totals**
- Baseline **does not contribute to txn count**

**Card: Monthly Summary**

- Total spend (big):
  - `txn_total` (sum of logged transactions in selected month)
  - + `baseline_total` (sum of wallet `cycle_spend_sgd`)
- Txn count:
  - count of logged transactions in selected month (baseline excluded)
- Top card:
  - determined by per-card spend including baseline:
    - `(sum txns for card in selected month) + (that card's cycle_spend_sgd)`
  - if all totals are 0, show "—"
- **UI positioning (layout polish):**
  - "Top Card" block should sit more to the right and slightly lower, aligned nearer the right-side thumbnail area

**Card: Transactions**

#### Section 1: PRIOR SPEND (display-only)
- If any wallet card has `cycle_spend_sgd > 0`, render a **“PRIOR SPEND”** header.
- Render baseline rows under it (not transactions):
  - Left: `{Card Name}` (truncate with ellipsis if needed)
  - Right: `$X.XX` (always fully visible)
- Baseline rules:
  - Not saved into `cardtrack_transactions`
  - Included in spend totals
  - Excluded from transaction count
- Add a **strong divider** after the Prior Spend section.
- Render 1 row per wallet card where `cycle_spend_sgd > 0`

#### Section 2: TRANSACTIONS
- Render a **“TRANSACTIONS”** header above the logged transactions list (selected month).
- Logged transactions show **faint dividers** between rows.
- Transaction row shows:
  - Item (left), Amount (right)
  - Sub-row: card chip + date (`D-MMM-YYYY`)
- Empty state (transactions only):
  - If **no logged transactions** in selected month:
    - show: “No transactions yet. Log a transaction from Recommend.”

**Card: Card Overview**

- For each wallet card:
  - thumbnail + name
  - Current month spend:
    - `(sum logged txns for that card/month) + (cycle_spend_sgd for that card)`
  - Annual fee date

---

## 4) Data Contract (CSV seed + LocalStorage)

### 4.1 Seed CSV Files (read-only)
Place under: `/public/data/`

#### `cards_master.csv`
Used for autocomplete + display metadata.

**Columns**
- `card_id` (string, unique)
- `card_name` (string)
- `issuer` (string)
- `reward_type` (`miles` | `cashback`)
- `image_path` (string; points to `/public/assets/cards/*`)

**Current rows**
```csv
card_id,card_name,issuer,reward_type,image_path
ww,DBS Woman's World Card,DBS,miles,/assets/cards/dbs_ww.png
prvi,UOB PRVI Miles Card,UOB,miles,/assets/cards/privi_miles.png
uobone,UOB One Card,UOB,cashback,/assets/cards/uobone.png
```

### 4.2 Assets

**Verified tick icon**
- File: `/public/assets/cards/tick.svg`
- Use in UI via: `src="/assets/cards/tick.svg"`

---

### 4.3 LocalStorage Keys (read/write)

#### Key: `cardtrack_user_profile`
Shape:
```json
{
  "user_id": "u_001",
  "username": "demo",
  "password": "demo",
  "preference": "miles",
  "wallet": [
    {
      "card_id": "ww",
      "refresh_day_of_month": 15,
      "annual_fee_billing_date": "2026-06-28",
      "cycle_spend_sgd": 700
    }
  ]
}
```

**Wallet fields**

- `card_id` *(string)*
- `refresh_day_of_month` *(int 1–31)*
- `annual_fee_billing_date` *(YYYY-MM-DD string)*
- `cycle_spend_sgd` *(number, SGD; default 0)* — baseline spend already incurred in current cycle:
  - displayed under Prior Spend on dashboard; **not a transaction**
  - **included in spend totals**
  - **excluded from txn count**

---

#### Key: `cardtrack_transactions`

**Shape:**
```json
[
  {
    "id": "t_0001",
    "date": "2026-02-12",
    "item": "GrabFood",
    "amount_sgd": 100,
    "card_id": "ww",
    "channel": "online",
    "is_overseas": false
  }
]
```

**Transaction Fields**

- `id` *(string)*
- `date` *(YYYY-MM-DD)*
- `item` *(string)*
- `amount_sgd` *(number)*
- `card_id` *(string)*
- `channel` *(online | offline)*
- `is_overseas` *(boolean; optional)*

**No seeding**
- Remains empty until user logs via Recommend

---

### 4.4 Recommendation Contract (UI adapter)

**Function:**
`getRecommendation({ userProfile, txn, transactions, cardsMaster }) -> RecommendationResult`

**Return shape:**
```json
{
  "recommended_card_id": "ww",
  "ranked_cards": [
    {
      "card_id": "ww",
      "reward_unit": "miles",
      "estimated_reward_value": 400,
      "effective_rate_str": "4.0 mpd",
      "explanations": [
        "You prefer miles, and this is an online transaction.",
        "DBS WW earns 4 mpd on eligible online spend (up to monthly cap).",
        "Baseline cycle spend is shown under Prior Spend on the dashboard and contributes to spend totals, but is not a transaction."
      ]
    }
  ],
  "state_snapshot": {
    "target_month": "2026-02"
  }
}
```

**Deterministic prototype logic (simple, no backend)**

- If `preference = miles` **AND** `channel = online` → rank **WW** first *(if in wallet)*
- Else → rank **PRVI** first *(if in wallet)*
- If `preference = cashback` → rank **UOB One** first *(if in wallet)*
- Remaining wallet cards appear next in a stable order
- Each ranked card must include **2–5** explanation bullets

---

## 5) Engineering Backlog (Claude tasks in build order)

### Epic 0 — Setup
- **E0.1** Scaffold Vite + React + Tailwind + Router  
- **E0.2** Global layout, background pattern, device frame  

### Epic 1 — Data Layer
- **E1.1** CSV loader (fetch `/data/cards_master.csv`, parse)  
- **E1.2** LocalStorage adapter:
  - `loadUserProfile()`, `saveUserProfile()`
  - `loadTransactions()`, `appendTransaction()`
  - helpers for month grouping
- **E1.3** Ensure no demo seeding logic exists for transactions  

### Epic 2 — Core Components (reusable)
- **E2.1** CardSurface  
- **E2.2** CardAutocomplete  
- **E2.3** SegmentedControl  
- **E2.4** VerifiedBadge  
- **E2.5** BottomNav  

### Epic 3 — Screen: Register
- **E3.1** Registration layout matching mock  
- **E3.2** Wallet cards repeatable block + add button  
- **E3.3** Add "Spent so far (this cycle)" field (`cycle_spend_sgd`)  
- **E3.4** Add "Next refresh" helper text computed robustly from refresh day + today (handle invalid days like Feb 30)  
- **E3.5** Validation + save profile + route to `/creating` then redirect to `/dashboard`  
- **E3.6** Remove step pill "Step 1 of 3: Create Profile"  
- **E3.7** Annual fee date required once a card is selected (inline red error on submit)  
- **E3.8** Copy updates: label "Refresh"; label "Spent so far (this cycle)"  

### Epic 4 — Screen: Recommend
- **E4.1** Transaction form UI  
- **E4.2** Implement `getRecommendation()` mock logic  
- **E4.3** Recommendation result card UI (rank, chips, bullets, show more)  
- **E4.4** Cursor loop: next best / exhausted state  
- **E4.5** Log transaction → persist → redirect dashboard  

### Epic 5 — Screen: Dashboard
- **E5.1** Month selector + month list of transactions  
- **E5.2** Monthly summary aggregation (`txn_total + baseline_total`; txn count excludes baseline)  
- **E5.3** Transactions list + empty state (Prior Spend section (display-only))  
- **E5.4** Card overview aggregation (per-card spend includes baseline + logged txns; annual fee date)  
- **E5.5** Render Prior Spend section (display-only rows from wallet `cycle_spend_sgd`; included in totals; excluded from txn count)
- **E5.6** Top Card positioning polish (right column alignment)  
- **E5.7** Transaction dates formatted as `D-MMM-YYYY`  
- **E5.8** Dividers: **strong divider after Prior Spend section** + faint dividers between transaction rows
- **E5.9** Prior Spend section header-based labeling (no "(Prior spend)" inline per row)

### Epic 6 — Polish
- **E6.1** Empty states + validations  
- **E6.2** Responsive refinements + spacing alignment  
- **E6.3** Hide scrollbar UI inside device frame (scroll remains functional)  
- **E6.4** Replace verified badge tick with `/assets/cards/tick.svg`