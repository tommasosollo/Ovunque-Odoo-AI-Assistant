# Release Notes - Ovunque v19.0.2.0.0

## 🎉 Major Feature: Multi-Model Queries

This release introduces **cross-model query capabilities** - a game-changer for complex Odoo searches.

### What's New

#### 1. **Multi-Model Query Support**
   - Query patterns that span **two Odoo models** automatically
   - **NO LLM needed** - uses pure pattern matching for reliability
   - Example: "Clienti con più di 10 fatture" (Clients with 10+ invoices)

#### 2. **Built-in Query Patterns**

| Pattern | Example Query | Operation |
|---------|---------------|-----------|
| `partners_with_count_invoices` | "Clienti con più di 10 fatture" | Count aggregation |
| `partners_with_orders` | "Clienti con 5+ ordini" | Count aggregation |
| `products_without_orders` | "Prodotti mai ordinati" | Exclusion |
| `suppliers_without_purchases` | "Fornitori senza acquisti" | Exclusion |

#### 3. **Two Operation Types**

**Count Aggregation**
- Groups secondary model records by primary model ID
- Counts per group
- Filters by threshold (N+)
- Returns matching primary model records

**Exclusion**
- Finds records in secondary model
- Returns primary model records NOT in that set
- Useful for "never", "without", "no" queries

### How It Works

```
User Query: "Clienti con più di 10 fatture"
                    ↓
[1] Regex Pattern Detection
    - Matches: partners_with_count_invoices
    - Extracts: threshold=10
                    ↓
[2] Execute Pattern Logic (NO API CALL!)
    - Search: account.move (all invoices)
    - Group by: partner_id
    - Count: per partner
    - Filter: count >= 10
                    ↓
[3] Return Results
    - Query: res.partner (matching partners)
    - Results: [Partner1, Partner3, Partner7]
```

### Performance Benefits

- **Instant**: No waiting for OpenAI API (~1-2 seconds total)
- **Free**: No API costs for multi-model queries
- **Reliable**: Pure pattern matching, no LLM hallucinations
- **Scalable**: Works with up to ~100k records per table

### Files Added

- `MULTI_MODEL_PATTERNS.md` - Complete guide to patterns and extensibility
- `test_multi_model.py` - Test script for pattern detection
- Updated `search_query.py` with multi-model logic
- Updated `README.md` with multi-model documentation

### Code Changes

#### In `models/search_query.py`

Added:
- `MULTI_MODEL_PATTERNS` - Dictionary of regex patterns and configurations
- `is_multi_model` field - Tracks if query is multi-model type
- `_detect_multi_model_query()` - Detects multi-model patterns
- `_execute_multi_model_search()` - Routes to appropriate operation
- `_execute_count_aggregate()` - Implements count aggregation logic
- `_execute_exclusion()` - Implements exclusion logic
- `_execute_single_model_search()` - Refactored single-model logic

Modified:
- `action_execute_search()` - Added multi-model detection and routing
- Added imports: `re`, `Counter`

### Backward Compatibility

✅ **100% backward compatible**
- All existing single-model queries work exactly as before
- Multi-model detection is automatic
- No configuration needed

### Usage Examples

#### Example 1: Count Aggregation
```
Query: "Clienti con più di 5 fatture"

Flow:
1. Detect pattern: partners_with_count_invoices
2. Query account.move: count(partner_id)
3. Filter: count >= 5
4. Return: matching res.partner records

Result: All customers with 5+ invoices
```

#### Example 2: Exclusion
```
Query: "Prodotti mai ordinati"

Flow:
1. Detect pattern: products_without_orders
2. Query sale.order: get all product_ids
3. Find: product.template NOT in above list
4. Return: matching product.template records

Result: All products with zero sales
```

### Extending with Custom Patterns

Adding a new pattern takes **3 minutes**:

```python
# 1. Add to MULTI_MODEL_PATTERNS dictionary
'my_custom_pattern': {
    'pattern': r'(your|keywords).*?regex',
    'primary_model': 'res.partner',
    'secondary_model': 'account.move',
    'operation': 'count_aggregate',
    'aggregate_field': 'partner_id',
    'link_field': 'partner_id',
}

# 2. Test the regex with user queries

# 3. Done! System auto-detects and executes
```

See `MULTI_MODEL_PATTERNS.md` for detailed guide.

### Logging

New log prefixes for debugging:
- `[MULTI-MODEL]` - Detection and initialization
- `[MULTI-MODEL-AGG]` - Count aggregation execution
- `[MULTI-MODEL-EXC]` - Exclusion execution

Example:
```
tail -f /var/log/odoo/odoo.log | grep '[MULTI-MODEL]'
```

### Testing

Run the test script:
```bash
./odoo-bin shell
exec(open('/path/to/addons/ovunque/test_multi_model.py').read())
```

Or test manually in Ovunque UI:
- Try: "Clienti con più di 5 fatture"
- Try: "Prodotti mai ordinati"
- Check logs for `[MULTI-MODEL]` markers

### Documentation

- `README.md` - Updated with multi-model overview and examples
- `MULTI_MODEL_PATTERNS.md` - Complete reference for patterns
- `test_multi_model.py` - Test examples
- Inline code comments - Explain each method

### Roadmap for Future Versions

- [ ] Support 3+ table correlations
- [ ] Add temporal patterns (e.g., "not contacted in 6 months")
- [ ] SQL optimization for large datasets
- [ ] Pattern learning from user feedback
- [ ] UI wizard for creating patterns

### Breaking Changes

None! This release is 100% backward compatible.

### Migration Notes

No migration needed. Update the module, restart Odoo, and multi-model queries work automatically.

### Bug Fixes in This Release

- Improved error messages for field validation
- Better handling of edge cases in domain parsing
- Fixed price field confusion in more scenarios

### Known Limitations

- Multi-model queries limited to 2 models (by design, for simplicity)
- Patterns must be hardcoded (no dynamic pattern creation yet)
- Maximum ~100k records per table for optimal performance
- Some pattern combinations may require custom implementation

### Support

- **Documentation**: See `MULTI_MODEL_PATTERNS.md`
- **Debug logs**: Filter for `[MULTI-MODEL]` in odoo.log
- **Test script**: Run `test_multi_model.py` in Odoo shell
- **Field inspection**: Use `/ovunque/debug-fields?model=model.name`

### Contributors

This feature was developed with focus on:
- **Simplicity**: Pure Python, no SQL magic
- **Reliability**: No LLM, no hallucinations
- **Extensibility**: Easy to add new patterns
- **Performance**: Fast execution, no API latency

### Version History

- **v19.0.2.0.0** (Current) - Multi-model queries, pattern-based matching
- **v19.0.1.0.0** - Initial release with GPT-4 integration

---

## 📚 Complete Documentation

- **Main README**: `README.md`
- **Pattern Guide**: `MULTI_MODEL_PATTERNS.md` (NEW)
- **Development Guide**: `addons/ovunque/DEVELOPMENT.md`
- **Debug Guide**: `CLAUDE.md`
- **Test Script**: `addons/ovunque/test_multi_model.py` (NEW)

---

## 🎯 Next Steps

1. **Update your Odoo module** to v19.0.2.0.0
2. **Test multi-model queries** in the UI
3. **Read `MULTI_MODEL_PATTERNS.md`** to understand extensibility
4. **Add custom patterns** for your business needs
5. **Monitor logs** with `[MULTI-MODEL]` filter

---

**Thank you for using Ovunque! Happy searching! 🔍**
