"""
Test script for multi-model queries.

This script tests the multi-model query functionality with real Odoo data.
Usage: ./odoo-bin shell
        exec(open('/path/to/test_multi_model.py').read())
"""

import logging
_logger = logging.getLogger(__name__)

print("\n" + "="*80)
print("OVUNQUE MULTI-MODEL QUERY TEST")
print("="*80 + "\n")

SearchQuery = env['search.query']

# Test cases: (query, expected_primary_model, expected_operation)
test_cases = [
    # Count Aggregate Tests
    (
        "Clienti con più di 5 fatture",
        'res.partner',
        'count_aggregate',
        5,
    ),
    (
        "Customers with 10+ invoices",
        'res.partner',
        'count_aggregate',
        10,
    ),
    (
        "Partners con 3 ordini",
        'res.partner',
        'count_aggregate',
        3,
    ),
    # Exclusion Tests
    (
        "Prodotti mai ordinati",
        'product.template',
        'exclusion',
        None,
    ),
    (
        "Products without orders",
        'product.template',
        'exclusion',
        None,
    ),
]

print("Testing multi-model pattern detection...\n")

for i, test_case in enumerate(test_cases, 1):
    if len(test_case) == 4:
        query_text, expected_model, expected_op, expected_count = test_case
    else:
        query_text, expected_model, expected_op, expected_count = test_case + (None,)
    
    print(f"Test {i}: {query_text}")
    print("-" * 80)
    
    # Create a search query record
    query = SearchQuery.create({'name': query_text})
    
    # Detect multi-model pattern
    pattern = query._detect_multi_model_query()
    
    if pattern:
        print(f"✓ Pattern detected: {pattern['pattern_key']}")
        print(f"  Primary model: {pattern['primary_model']}")
        print(f"  Secondary model: {pattern['secondary_model']}")
        print(f"  Operation: {pattern['operation']}")
        if 'count_value' in pattern:
            print(f"  Threshold: {pattern['count_value']}")
        
        # Verify expectations
        checks = [
            ("Primary model", pattern['primary_model'] == expected_model, 
             f"{pattern['primary_model']} == {expected_model}"),
            ("Operation", pattern['operation'] == expected_op,
             f"{pattern['operation']} == {expected_op}"),
        ]
        
        if expected_count and 'count_value' in pattern:
            checks.append(("Threshold", pattern['count_value'] == expected_count,
                          f"{pattern['count_value']} == {expected_count}"))
        
        all_pass = True
        for check_name, result, details in checks:
            status = "✓" if result else "✗"
            print(f"  {status} {check_name}: {details}")
            if not result:
                all_pass = False
        
        if all_pass:
            print("✓ Test PASSED")
        else:
            print("✗ Test FAILED")
    else:
        print("✗ No pattern detected (expected pattern to be detected)")
    
    query.unlink()
    print()

print("="*80)
print("TEST SUMMARY")
print("="*80)
print("\nTo run actual queries, use:")
print("  1. Go to Ovunque → Query Search in Odoo UI")
print("  2. Try these test queries:")
print("     - 'Clienti con più di 5 fatture'")
print("     - 'Prodotti mai ordinati'")
print("     - 'Fornitori senza acquisti'")
print("\nTo debug individual queries, check logs:")
print("  tail -f /var/log/odoo/odoo.log | grep '[MULTI-MODEL]'")
print("\n" + "="*80 + "\n")
