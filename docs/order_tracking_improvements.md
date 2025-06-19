# Order Tracking Improvements for Lighter CPTY

## Current State
Orders are tracked only in memory:
- `self.orders`: Maps client order ID to order object
- `self.client_to_exchange_id`: Maps client ID to exchange ID
- `self.exchange_to_client_id`: Maps exchange ID to client ID

## Recommended Improvements

### 1. Add Database Persistence
```python
import sqlite3

class OrderDatabase:
    def __init__(self, db_path="orders.db"):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()
    
    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                cl_ord_id TEXT PRIMARY KEY,
                exchange_id TEXT,
                symbol TEXT,
                side TEXT,
                price REAL,
                qty REAL,
                filled_qty REAL DEFAULT 0,
                status TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
    
    def save_order(self, order, exchange_id):
        # Save order to database
        pass
    
    def update_order_status(self, cl_ord_id, status, filled_qty=None):
        # Update order status
        pass
```

### 2. Fix WebSocket for Real-time Updates
The WebSocket currently fails due to `extra_headers` parameter issue. Need to fix the connection to get:
- Order fills
- Order cancellations
- Position updates

### 3. Add Order Status Polling
Since Lighter doesn't have a direct "get open orders" API, implement periodic status checks:

```python
async def poll_order_status(self):
    """Poll order status periodically."""
    while True:
        for cl_ord_id, order in self.orders.items():
            if order.status in ['NEW', 'PARTIALLY_FILLED']:
                # Check order status somehow
                # Update if filled or cancelled
                pass
        await asyncio.sleep(5)  # Poll every 5 seconds
```

### 4. Track Order Lifecycle
```python
class OrderTracker:
    def __init__(self):
        self.orders = {}
        self.order_history = []
    
    def on_order_placed(self, order, exchange_id):
        self.orders[order.cl_ord_id] = {
            'order': order,
            'exchange_id': exchange_id,
            'status': 'NEW',
            'filled_qty': 0,
            'created_at': datetime.now(),
            'updates': []
        }
    
    def on_order_fill(self, cl_ord_id, filled_qty, fill_price):
        # Update order with fill info
        pass
    
    def on_order_cancelled(self, cl_ord_id):
        # Mark order as cancelled
        pass
```

### 5. Implement Reconciliation
When Architect requests open orders, actually check with Lighter:
- Query recent transactions
- Match against known orders
- Update statuses accordingly

## Current Workaround
For now, you can:
1. Track orders externally in your own database
2. Use the transaction hash to check order status on Lighter's frontend
3. Implement your own WebSocket connection to Lighter for updates