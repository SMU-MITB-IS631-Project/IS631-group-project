# CardTrack Backend API

Python FastAPI backend implementing the CardTrack API Contract (v0.1).

**Branch:** `SCRUM-178-create-post-transactions-endpoint`  
**Jira:** SCRUM-178 - Create Post Transactions Endpoint

## Project Structure

```
backend/
├── app/
│   ├── models/          # Pydantic models for request/response validation
│   │   └── transaction.py
│   ├── routes/          # API endpoint handlers
│   │   └── transactions.py
│   ├── services/        # Business logic & data access layer
│   │   └── data_service.py
│   └── main.py          # FastAPI app setup & configuration
├── data/                # JSON file storage (gitignored)
├── run.py               # Server startup script
└── requirements.txt     # Python dependencies
```

## Quick Start

### Prerequisites
- Python 3.11+ installed
- pip package manager

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Run the Server

```bash
python run.py
```

Server starts at **`http://localhost:8000`** with auto-reload enabled.

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Testing the API

### Option 1: Interactive API Docs (Swagger UI) — **Recommended**

1. Start the server: `python run.py`
2. Open browser: **http://localhost:8000/api/docs**
3. You'll see interactive documentation with all endpoints
4. Click on `POST /api/v1/transactions` → **"Try it out"**
5. Edit the request body:
   ```json
   {
     "transaction": {
       "item": "GrabFood",
       "amount_sgd": 100,
       "card_id": "ww",
       "channel": "online",
       "is_overseas": false
     }
   }
   ```
6. Click **"Execute"** to test the endpoint
7. View the response below

### Option 2: PowerShell/Command Line

**Create a Transaction:**
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/v1/transactions `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"transaction": {"item": "Taxi", "amount_sgd": 25.50, "card_id": "ww", "channel": "offline", "is_overseas": false}}'
```

**List All Transactions:**
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/v1/transactions -Method GET
```

### Option 3: curl (macOS/Linux/Git Bash)

**Create a Transaction:**
```bash
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '{"transaction": {"item": "GrabFood", "amount_sgd": 100, "card_id": "ww", "channel": "online", "is_overseas": false}}'
```

**List All Transactions:**
```bash
curl http://localhost:8000/api/v1/transactions
```

---

## API Endpoints

### `POST /api/v1/transactions`
Create a new transaction.

**Request:**
```json
{
  "transaction": {
    "item": "GrabFood",
    "amount_sgd": 100,
    "card_id": "ww",
    "channel": "online",
    "is_overseas": false
  }
}
```

**Response (201):**
```json
{
  "transaction": {
    "id": "a1b2c3d4",
    "date": "2026-02-10",
    "item": "GrabFood",
    "amount_sgd": 100,
    "card_id": "ww",
    "channel": "online",
    "is_overseas": false
  }
}
```

**Validation:**
- `item` required
- `amount_sgd` required, > 0
- `card_id` must exist in user's wallet
- `channel` must be `online` or `offline`

**Error Response (400):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "card_id 'invalid_card' not found in user wallet",
    "details": {}
  }
}
```

### `GET /api/v1/transactions`

List all transactions for the current user.

**Response (200):**
```json
{
  "transactions": [
    {
      "id": "a1b2c3d4",
      "date": "2026-02-10",
      "item": "GrabFood",
      "amount_sgd": 100,
      "card_id": "ww",
      "channel": "online",
      "is_overseas": false,
      "user_id": "u_001"
    }
  ]
}
```

---

## Implementation Details

### Data Storage

Currently uses **JSON file storage** (development only):
- `backend/data/users.json` - User profiles and card wallets
- `backend/data/transactions.json` - All transaction records

**Sample data** is auto-initialized on server startup.

#### `users.json` Structure

Stores user profiles with their card wallets:

```json
{
  "u_001": {
    "user_id": "u_001",
    "username": "demo",
    "preference": "miles",
    "wallet": [
      {
        "card_id": "ww",
        "refresh_day_of_month": 15,
        "annual_fee_billing_date": "2026-06-28",
        "cycle_spend_sgd": 700
      },
      {
        "card_id": "tuvalu",
        "refresh_day_of_month": 20,
        "annual_fee_billing_date": "2026-07-15",
        "cycle_spend_sgd": 500
      }
    ]
  }
}
```

**Fields:**
- `user_id`: Unique user identifier (currently hardcoded to `u_001`)
- `username`: Display name
- `preference`: User's reward preference (`miles` or `cashback`)
- `wallet`: Array of cards owned by the user
  - `card_id`: Card identifier (must match cards in `cards_master.csv`)
  - `refresh_day_of_month`: Spending cycle reset day (1-31)
  - `annual_fee_billing_date`: When annual fee is charged
  - `cycle_spend_sgd`: Baseline/prior spending amount

#### `transactions.json` Structure

Stores all transactions organized by user:

```json
{
  "u_001": [
    {
      "id": "26380ddd",
      "date": "2026-02-10",
      "item": "GrabFood",
      "amount_sgd": 100.0,
      "card_id": "ww",
      "channel": "online",
      "is_overseas": false,
      "user_id": "u_001"
    }
  ]
}
```

**Fields:**
- `id`: Auto-generated unique transaction ID
- `date`: Transaction date (auto-set to today if not provided)
- `item`: Transaction description/merchant
- `amount_sgd`: Transaction amount in SGD
- `card_id`: Card used (must exist in user's wallet)
- `channel`: `online` or `offline`
- `is_overseas`: Whether transaction occurred overseas
- `user_id`: Owner of the transaction

**Note:** The `data/` folder is gitignored, so test data won't be committed to the repository.

### Validation Rules

Per API Contract specification:
- ✅ Transaction `item` is required
- ✅ `amount_sgd` must be > 0
- ✅ `card_id` must exist in user's wallet
- ✅ `channel` must be `online` or `offline`
- ✅ Server auto-generates transaction `id`
- ✅ Server sets `date` to today if not provided

### CORS

CORS is enabled for frontend integration:
- Allowed origins: `http://localhost:5173`, `http://localhost:3000`, and all (`*`)

---

## Development Notes

### Adding New Endpoints

1. **Create model** in `app/models/your_model.py`
2. **Create route** in `app/routes/your_route.py`
3. **Import and register** router in `app/main.py`:
   ```python
   from app.routes import your_router
   app.include_router(your_router)
   ```

### Auto-Reload

The server runs with `reload=True` — any code changes automatically restart the server.

---

## Troubleshooting

### Port Already in Use

If you see `Error: [WinError 10013]`, port 8000 is already in use:
1. Stop any other servers running on port 8000
2. Or change the port in `run.py`: `port=8001`

### Module Not Found Errors

Make sure you're in the correct directory:
```bash
cd backend
pip install -r requirements.txt
python run.py
```

### Dependencies Installation Issues

If packages fail to install, try:
```bash
pip install --upgrade pip setuptools
pip install -r requirements.txt
```

---

## Next Steps / TODO

- [ ] Add authentication (retrieve `user_id` from auth token)
- [ ] Migrate to PostgreSQL/SQLite database
- [ ] Add transaction filtering by month/date
- [ ] Implement remaining API contract endpoints (recommendations, profile, etc.)
- [ ] Add unit tests
- [ ] Add integration tests

---

## API Contract Reference

Full API specification: [`frontend/api_contract/API_CONTRACT.md`](../frontend/api_contract/API_CONTRACT.md)

This implementation follows the CardTrack API Contract v0.1.
