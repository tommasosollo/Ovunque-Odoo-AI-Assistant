# Multi-Model Query Patterns

This file documents the available multi-model patterns and how to extend them.

## Built-in Patterns

### 1. Partners with Count Invoices

**Description**: Find customers/suppliers with N or more invoices

**Pattern Name**: `partners_with_count_invoices`

**Example Queries**:
- "Clienti con più di 10 fatture"
- "Customers with 5+ invoices"
- "Fornitori con almeno 20 documenti"

**How it works**:
1. Count all account.move records grouped by partner_id
2. Filter partners with count >= threshold
3. Return matching res.partner records

**Regex Pattern**:
```
r'(clienti|partner|cliente|customer|fornitore|supplier).*?(?:con|that have|with).*?(\d+)\s*(?:fatture|invoice|document)'
```

---

### 2. Partners with Count Orders

**Description**: Find customers with N or more sales/purchase orders

**Pattern Name**: `partners_with_orders`

**Example Queries**:
- "Clienti con più di 5 ordini"
- "Customers with 10+ orders"
- "Fornitori con 3+ acquisti"

**How it works**:
1. Count all sale.order records grouped by partner_id
2. Filter partners with count >= threshold
3. Return matching res.partner records

---

### 3. Products without Orders

**Description**: Find products that have never been ordered

**Pattern Name**: `products_without_orders`

**Example Queries**:
- "Prodotti mai ordinati"
- "Products never ordered"
- "Articoli senza ordini"

**How it works**:
1. Find all product IDs referenced in sale.order
2. Return product.template records NOT in that list
3. Excludes products with zero sales

---

### 4. Suppliers without Purchases

**Description**: Find suppliers with no purchase orders

**Pattern Name**: `suppliers_without_purchases`

**Example Queries**:
- "Fornitori senza acquisti"
- "Suppliers without orders"
- "Partner non usato"

**How it works**:
1. Find all partner IDs referenced in purchase.order
2. Return res.partner records (filtered as suppliers) NOT in that list

---

## How to Add a New Pattern

### Step 1: Define Your Pattern

Identify:
- Primary model (what you want to return)
- Secondary model (what you'll count/filter from)
- Operation type (count_aggregate or exclusion)
- Linking field (how models relate)

### Step 2: Create the Regex Pattern

Write a regex that matches user queries:

```python
'your_pattern_name': {
    'pattern': r'YOUR_REGEX_HERE',
    'primary_model': 'model.you.want.to.return',
    'secondary_model': 'model.to.count.or.filter',
    'operation': 'count_aggregate',  # or 'exclusion'
    'aggregate_field': 'link_field_in_secondary_model',
    'link_field': 'link_field_in_secondary_model',
}
```

### Step 3: Add to MULTI_MODEL_PATTERNS

Edit `models/search_query.py` and add your pattern to the `MULTI_MODEL_PATTERNS` dictionary:

```python
MULTI_MODEL_PATTERNS = {
    'partners_with_count_invoices': { ... },
    'partners_with_orders': { ... },
    'products_without_orders': { ... },
    'suppliers_without_purchases': { ... },
    'YOUR_NEW_PATTERN': {  # ← Add here
        'pattern': r'(your|pattern).*?regex',
        'primary_model': 'res.partner',
        'secondary_model': 'account.move',
        'operation': 'count_aggregate',
        'aggregate_field': 'partner_id',
        'link_field': 'partner_id',
    },
}
```

### Step 4: Test Your Pattern

Test the regex with expected user queries:

```python
import re

pattern = r'(your|pattern).*?regex'
test_queries = [
    "Clienti con più di 10 fatture",
    "customers with 5+ invoices",
]

for query in test_queries:
    if re.search(pattern, query, re.IGNORECASE):
        print(f"✓ Matched: {query}")
    else:
        print(f"✗ Did not match: {query}")
```

### Step 5: Verify Data Linking

Make sure the `aggregate_field` and `link_field` are correct:

- `aggregate_field`: Field in secondary model that links to primary model
  - Example: In account.move, "partner_id" links to res.partner
  
- `link_field`: Same field name (used for grouping/filtering)
  - Example: "partner_id" in account.move

---

## Pattern Configuration Reference

### Field Descriptions

```python
{
    'pattern': r'regex_pattern',
    # ↑ Regular expression to match user queries
    # Example: r'(clienti|customer).*?con.*?(\d+).*?fatture'
    
    'primary_model': 'model.name',
    # ↑ The model to return results from
    # Example: 'res.partner' (we return customers)
    
    'secondary_model': 'model.name',
    # ↑ The model to count/filter records from
    # Example: 'account.move' (we count invoices)
    
    'operation': 'count_aggregate',
    # ↑ Type of operation:
    #   - 'count_aggregate': Count secondary records per primary, filter by threshold
    #   - 'exclusion': Find primary records NOT in secondary
    
    'aggregate_field': 'field_name',
    # ↑ Field in secondary model that links to primary model
    # Example: 'partner_id' in account.move
    
    'link_field': 'field_name',
    # ↑ Usually same as aggregate_field
    # Used to extract the primary model ID from secondary records
}
```

---

## Operation Types

### count_aggregate

**Use when**: You want to find primary model records with N+ related records in secondary model

**Example**: "Clients with 10+ invoices"

**Process**:
1. Search all secondary model records
2. Group by primary model ID (via link_field)
3. Count records per group
4. Filter groups where count >= threshold
5. Return matching primary model records

**Configuration**:
```python
{
    'operation': 'count_aggregate',
    'aggregate_field': 'partner_id',
    'link_field': 'partner_id',
}
```

---

### exclusion

**Use when**: You want to find primary model records NOT present in secondary model

**Example**: "Products never ordered"

**Process**:
1. Search all secondary model records
2. Extract unique primary model IDs (via link_field)
3. Find primary model records NOT in that set
4. Return those records

**Configuration**:
```python
{
    'operation': 'exclusion',
    'aggregate_field': 'product_id',
    'link_field': 'product_id',
}
```

---

## Common Issues

### Pattern Not Matching

**Problem**: Your regex pattern doesn't match user queries

**Solution**:
1. Test the regex with real queries
2. Check for case sensitivity (use `re.IGNORECASE` flag)
3. Test regex online at https://regex101.com
4. Make sure keywords match expected user input

### Wrong Model Selected

**Problem**: The operation finds results but from the wrong model

**Solution**:
1. Verify `primary_model` is what you want to return
2. Verify `secondary_model` is where you're counting/filtering
3. Check `link_field` points to the correct reference field
4. Use `/ovunque/debug-fields?model=model.name` to verify field names

### No Results

**Problem**: Query matches but returns empty results

**Solution**:
1. Check the logs for `[MULTI-MODEL-AGG]` or `[MULTI-MODEL-EXC]` messages
2. Verify threshold value is extracted correctly
3. Make sure secondary model has data
4. For count_aggregate, check if count >= threshold (use > for "more than", >= for "or more")

---

## Examples for Different Industries

### E-Commerce

```python
'customers_with_high_orders': {
    'pattern': r'(client|customer|acquirente).*?(?:con|with).*?(\d+)\s*ordini.*?(?:oltre|sopra|above|over)\s*(\d+)',
    'primary_model': 'res.partner',
    'secondary_model': 'sale.order',
    'operation': 'count_aggregate',
    'aggregate_field': 'partner_id',
    'link_field': 'partner_id',
}
```

### Manufacturing

```python
'suppliers_with_late_deliveries': {
    'pattern': r'(fornitore|supplier).*?(?:ritardi|late|delay)',
    'primary_model': 'res.partner',
    'secondary_model': 'purchase.order',
    'operation': 'exclusion',  # Would need custom logic for "late"
    'aggregate_field': 'partner_id',
    'link_field': 'partner_id',
}
```

### Inventory

```python
'slow_moving_products': {
    'pattern': r'(prodotto|product).*?(?:non venduto|never sold|zero sale)',
    'primary_model': 'product.template',
    'secondary_model': 'sale.order',
    'operation': 'exclusion',
    'aggregate_field': 'product_id',
    'link_field': 'product_id',
}
```

---

## Advanced: Creating Custom Operations

To add a new operation type beyond `count_aggregate` and `exclusion`:

1. Add pattern with `'operation': 'your_operation'` to `MULTI_MODEL_PATTERNS`

2. Create method in `SearchQuery` class:
```python
def _execute_your_operation(self, primary_model_name, secondary_model_name,
                           pattern_config, PrimaryModel, SecondaryModel):
    """Your custom operation logic here"""
    # Implement your logic
    # Set: self.result_ids, self.results_count, self.model_domain, self.status
```

3. Add handler to `_execute_multi_model_search()`:
```python
elif operation == 'your_operation':
    self._execute_your_operation(...)
```

---

## Logging & Debugging

Multi-model queries generate detailed logs with prefixes:

- `[MULTI-MODEL]` - Detection and routing
- `[MULTI-MODEL-AGG]` - Count aggregation execution
- `[MULTI-MODEL-EXC]` - Exclusion execution

To view logs:
```bash
tail -f /var/log/odoo/odoo.log | grep '\[MULTI-MODEL\]'
```

---

## Performance Considerations

Multi-model queries search full secondary model tables, which can be slow with large datasets.

**Optimization tips**:

1. **Add domain filters**: Modify secondary model search to add filters
   ```python
   # Current: SecondaryModel.search([])
   # Better: SecondaryModel.search([('date', '>=', '2025-01-01')])
   ```

2. **Use SQL aggregation**: For very large tables, use raw SQL
   ```python
   self.env.cr.execute("SELECT partner_id, COUNT(*) FROM account_move GROUP BY partner_id")
   ```

3. **Cache results**: Store aggregation results periodically
   ```python
   # Compute once daily, retrieve from cache
   ```

---

## Need Help?

- Check the logs with `[MULTI-MODEL]` prefix
- Review examples in this file
- Test regex pattern at https://regex101.com
- Inspect model fields with `/ovunque/debug-fields?model=model.name`
