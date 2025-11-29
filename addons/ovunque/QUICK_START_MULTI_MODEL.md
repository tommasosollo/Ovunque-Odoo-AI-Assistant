# Quick Start: Multi-Model Queries

**TL;DR - Try these queries NOW:**

```
"Clienti con più di 10 fatture"
"Fornitori senza acquisti"
"Prodotti mai ordinati"
```

---

## What Are Multi-Model Queries?

Normal: "Show unpaid invoices" → Search one table (account.move)

Multi-Model: "Show clients with 10+ invoices" → Search TWO tables, correlate results

```
Step 1: Search account.move (all invoices)
Step 2: Group by customer
Step 3: Count per customer
Step 4: Filter: count >= 10
Step 5: Return res.partner (customers)
```

**Result**: All customers with 10+ invoices ✓

---

## Supported Patterns (Built-In)

### Count Aggregation (Find records with N+)

| Pattern | Try This Query |
|---------|---|
| Clients with N invoices | "Clienti con più di 10 fatture" |
| Customers with N orders | "Clienti con 5+ ordini" |
| Partners with N documents | "Partner con almeno 3 documenti" |

**How**: Counts related records and filters by threshold

---

### Exclusion (Find records NOT related to another model)

| Pattern | Try This Query |
|---------|---|
| Products never ordered | "Prodotti mai ordinati" |
| Suppliers without purchases | "Fornitori senza acquisti" |
| Partners with no invoices | "Partner senza fatture" |

**How**: Finds records that don't exist in another table

---

## Usage

### In Ovunque UI

1. **Go to**: Ovunque → Query Search
2. **Type**: "Clienti con più di 10 fatture"
3. **Click**: Search
4. **See**: All matching customers instantly ⚡

That's it!

---

## Performance

| Query Type | Speed | Cost |
|---|---|---|
| Single-model (LLM-based) | ~2-3 seconds | ~0.01¢ per query |
| **Multi-model (pattern-based)** | **~1 second** | **FREE** |

---

## Examples in Action

### Example 1: Customers with 10+ Invoices

```
Query: "Clienti con più di 10 fatture"

Detection: ✓ Matched partners_with_count_invoices

Execution:
  1. Query account.move (get all invoices)
  2. Count by partner_id
     Partner 1: 15 invoices ✓
     Partner 2: 3 invoices  ✗
     Partner 3: 12 invoices ✓
  3. Return: Partner 1, Partner 3

Results: 2 customers with 10+ invoices
```

### Example 2: Never-Ordered Products

```
Query: "Prodotti mai ordinati"

Detection: ✓ Matched products_without_orders

Execution:
  1. Query sale.order (find all ordered products)
     Ordered: [Product1, Product2, Product3]
  2. Return products NOT in list
     All Products: [P1, P2, P3, P4, P5, P6]
     Never Ordered: [P4, P5, P6]

Results: 3 products with zero sales
```

---

## Troubleshooting

### "No results found"

Check the **Debug Info** tab:
1. Is `is_multi_model` = True?
2. Does the log say `[MULTI-MODEL]`?
3. Try rephrase: "Clienti con più di 5 fatture" instead of "Clienti con tante fatture"

### "Wrong pattern matched"

Your query might match multiple patterns. Be more specific:
- ❌ "Clienti" → Too vague
- ✅ "Clienti con più di 10 fatture" → Specific

### Need more help?

1. Check logs: `grep '[MULTI-MODEL]' /var/log/odoo/odoo.log`
2. Read full guide: `MULTI_MODEL_PATTERNS.md`
3. Run tests: `./odoo-bin shell` then `exec(open('test_multi_model.py').read())`

---

## Adding Your Own Pattern (Advanced)

Takes 3 minutes!

### Step 1: Choose your pattern
```
What do I want to find? → Customers
What should I count? → Invoices
How many? → More than 10
```

### Step 2: Edit `models/search_query.py`

Find `MULTI_MODEL_PATTERNS` and add:

```python
'customers_high_volume': {
    'pattern': r'(clienti|customer).*?alto.*?volume|volume.*?alto',
    'primary_model': 'res.partner',
    'secondary_model': 'account.move',
    'operation': 'count_aggregate',
    'aggregate_field': 'partner_id',
    'link_field': 'partner_id',
}
```

### Step 3: Test

```bash
./odoo-bin shell
exec(open('/path/to/test_multi_model.py').read())
```

Done! Your pattern works automatically.

---

## Pattern Cheat Sheet

### Count Aggregation Pattern

```python
{
    'pattern': r'REGEX_HERE',  # Matches user query
    'primary_model': 'res.partner',  # Return THIS model
    'secondary_model': 'account.move',  # Count records from THIS
    'operation': 'count_aggregate',
    'aggregate_field': 'partner_id',  # How they link
    'link_field': 'partner_id',
}
```

### Exclusion Pattern

```python
{
    'pattern': r'REGEX_HERE',
    'primary_model': 'product.template',
    'secondary_model': 'sale.order',
    'operation': 'exclusion',  # Find NOT in secondary
    'aggregate_field': 'product_id',
    'link_field': 'product_id',
}
```

---

## FAQ

**Q: Does this use OpenAI API?**
A: No! Multi-model queries use pattern matching. Single-model queries use GPT-4.

**Q: Why no cost?**
A: No API call = no cost. Pure Python logic.

**Q: Can I add my own patterns?**
A: Yes! Edit `MULTI_MODEL_PATTERNS` dict. See `MULTI_MODEL_PATTERNS.md` for details.

**Q: How many tables can I join?**
A: Currently 2 tables. 3+ tables would require custom code.

**Q: Is it faster than SQL?**
A: For these patterns, yes! No database JOINs, just Python grouping.

---

## Real-World Use Cases

### E-Commerce
- "Customers with 20+ orders"
- "Products never sold"
- "Vendors without recent purchases"

### Manufacturing
- "Suppliers with 100+ purchase orders"
- "Materials without BOM"
- "Production lines with zero output"

### Services
- "Clients with 5+ invoices"
- "Partners without contracts"
- "Projects with no tasks"

---

## Next Steps

1. **Try it now**: Search "Clienti con più di 10 fatture" in Ovunque
2. **Read more**: Open `MULTI_MODEL_PATTERNS.md`
3. **Add patterns**: Create your own in 3 minutes
4. **Monitor**: Check logs for `[MULTI-MODEL]` markers

---

**That's it! You're ready to use multi-model queries! 🚀**

Questions? Check `MULTI_MODEL_PATTERNS.md` for complete documentation.
