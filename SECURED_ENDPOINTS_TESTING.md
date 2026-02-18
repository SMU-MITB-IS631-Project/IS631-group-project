# Secured Endpoints Testing (Terminal)

These endpoints require the `x-user-id` header. Use the PowerShell commands below to test them from the terminal, or use the Postman collection.

## Testing Options

### Option 1: PowerShell Terminal (Quick Testing)

Use the commands below for quick testing from terminal.

### Option 2: Postman (Recommended for Team Testing)

1. **Import the collection**: Open Postman and import `POSTMAN_COLLECTION.json` from the project root
2. **Select an endpoint**: Navigate through the folders (Transactions, User Cards, etc.)
3. **Review the request**: Check the Headers tab (x-user-id is pre-configured) and Body tab (for POST/PUT requests)
4. **Click Send**: Test the endpoint and view the response

All endpoints are pre-configured with:
- Base URL: `http://localhost:8000`
- Headers: `x-user-id` set to `u_001`
- Request bodies: Sample payloads ready to use

## Base URL

- Local API: http://localhost:8000

## Required Header

- `x-user-id: u_001` (example user context)

## PowerShell Examples

### Get all transactions

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/transactions" -Headers @{"x-user-id"="u_001"} |
  ConvertTo-Json -Depth 6
```

### Get transactions by user ID

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/transactions/1?sort=date_desc" -Headers @{"x-user-id"="u_001"} |
  ConvertTo-Json -Depth 6
```

### Create a transaction

```powershell
$payload = @{
  transaction = @{
    card_id = 1
    amount_sgd = 15.50
    item = "Cinema Ticket"
    channel = "offline"
    category = "entertainment"
    is_overseas = $false
    date = "2026-02-18"
  }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/transactions" -Headers @{"x-user-id"="u_001"} -ContentType "application/json" -Body $payload |
  ConvertTo-Json -Depth 6
```

**Fields:**
- `card_id` (int): Card ID from wallet
- `amount_sgd` (decimal): Transaction amount
- `item` (string): Item description
- `channel` (string): `online` or `offline`
- `category` (string, optional): `food`, `travel`, `shopping`, `bills`, `entertainment`, or `others`
- `is_overseas` (boolean, optional): Default `false`
- `date` (string, optional): YYYY-MM-DD format; defaults to today if omitted

### Get user cards

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/user_cards" -Headers @{"x-user-id"="u_001"} |
  ConvertTo-Json -Depth 6
```

### Add user card

```powershell
$payload = @{
  wallet_card = @{
    card_id = "1"
    refresh_day_of_month = 15
    annual_fee_billing_date = "2026-06-28"
    cycle_spend_sgd = 700
  }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/user_cards" -Headers @{"x-user-id"="u_001"} -ContentType "application/json" -Body $payload |
  ConvertTo-Json -Depth 6
```

### Get wallet

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/wallet" -Headers @{"x-user-id"="u_001"} |
  ConvertTo-Json -Depth 6
```

## Notes

- `Invoke-RestMethod` prints JSON directly in the terminal.
- If you want raw headers and status codes, use `Invoke-WebRequest` instead.
