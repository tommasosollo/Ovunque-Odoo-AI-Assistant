"""
Debug script to list all stored fields for each available model.

This script is designed to be executed from the Odoo shell and provides
developers/admins with a comprehensive view of which fields are stored
(can be used in queries) vs computed (cannot be used).

Usage in Odoo shell:
    ./odoo-bin shell
    exec(open('/path/to/addons/ovunque/debug_fields.py').read())

Output:
    Displays a formatted table for each model showing:
    - All stored fields with their type and label
    - Count of stored fields
    - Notes about how to use Many2one and numeric fields in queries

This is useful for:
- Diagnosing why LLM generates invalid field names
- Understanding model structure
- Building custom search queries
"""

import logging

_logger = logging.getLogger(__name__)

# All models supported by Ovunque that can be debugged
AVAILABLE_MODELS = [
    'res.partner',
    'account.move',
    'product.product',
    'sale.order',
    'purchase.order',
    'stock.move',
    'crm.lead',
    'project.task',
]

print("\n" + "="*80)
print("AVAILABLE STORED FIELDS FOR OVUNQUE MODELS")
print("="*80 + "\n")

for model_name in AVAILABLE_MODELS:
    try:
        Model = env[model_name]
        fields_data = Model.fields_get()
        
        stored_fields = []
        for field_name, field_info in sorted(fields_data.items()):
            if field_name.startswith('_'):
                continue
            
            is_stored = field_info.get('store', True) is not False
            field_type = field_info.get('type', 'unknown')
            field_string = field_info.get('string', field_name)
            
            if is_stored:
                stored_fields.append((field_name, field_type, field_string))
        
        print(f"\n{'='*40}")
        print(f"Model: {model_name}")
        print(f"Total stored fields: {len(stored_fields)}")
        print(f"{'='*40}")
        
        for fname, ftype, fstring in stored_fields[:30]:
            print(f"  • {fname:30} ({ftype:15}) - {fstring}")
        
        if len(stored_fields) > 30:
            print(f"  ... and {len(stored_fields) - 30} more fields")
    
    except Exception as e:
        print(f"\n❌ Error loading {model_name}: {str(e)}")

print("\n" + "="*80)
print("NOTES:")
print("="*80)
print("- Use ONLY fields listed above in your queries")
print("- Fields not shown are either computed or virtual")
print("- For Many2one fields, use .name for text search")
print("  Example: [('partner_id.name', 'ilike', 'John')]")
print("- For numeric fields, don't use currency symbols")
print("  Example: [('list_price', '<', 100)]  ✓")
print("  Example: [('list_price', '<', '100€')]  ✗")
print("="*80 + "\n")
