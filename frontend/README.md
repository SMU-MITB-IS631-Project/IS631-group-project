# CardTrack — UI Prototype (Vite + React + Tailwind)

CardTrack is a **mobile-first UI prototype** for credit card recommendations and spend tracking.
It is **UI-only** (no backend) and persists data using **LocalStorage**. Card metadata is loaded from a seeded CSV.

## Tech Stack
- Vite + React
- TailwindCSS
- React Router
- LocalStorage (read/write)
- CSV seed file (read-only)

## Getting Started

### 1) Install
```bash
npm install
```
### 2) Run dev server
```bash
npm run dev
```
Open the local URL printed in the terminal (Vite uses 5173 by default, but will auto-pick another port if it’s busy).

## Seed Data & Assets

### CSV seed
Ensure this file exists:
- `public/data/cards_master.csv`

### Assets
Common paths:
- Card images: `public/assets/cards/*.png`
- Verified tick: `public/assets/cards/tick.svg`
- Background pattern (if present): `public/assets/backgrounds/*` *(or CSS data URI)*

---

## Routes
- `/register` — Create profile + wallet setup
- `/creating` — transient loading route after profile creation
- `/recommend` — enter transaction and get recommendation
- `/dashboard` — spend summary + transactions + card overview

**Routing guard**
- If no profile exists, all routes redirect to `/register`.

---

## LocalStorage Keys

### `cardtrack_user_profile`
Stores the user profile + wallet cards:
- Includes `cycle_spend_sgd` per card *(baseline “prior spend” for the cycle)*

### `cardtrack_transactions`
Array of logged transactions *(created only when user logs via Recommend)*:
- **No seeded transactions** are created automatically.

---

## Reset / Debug
To reset the app:
1. Open **DevTools** → **Application** → **LocalStorage**
2. Remove:
   - `cardtrack_user_profile`
   - `cardtrack_transactions`
3. Refresh the page

---

## Notes / Constraints
- Prototype is UI-only *(no real auth, no API)*.
- Baseline / prior spend:
  - contributes to spend totals
  - is **not** a transaction
  - does **not** count toward transaction count
- Recommendation engine is a deterministic mock (rule-based) used for UI prototyping (no backend / no real reward computation).


