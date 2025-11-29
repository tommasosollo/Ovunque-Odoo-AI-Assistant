# Ovunque - Natural Language Search for Odoo

**Search your Odoo data using conversational AI. Write queries like you're talking to a human.**

```
Input:  "Show me all unpaid invoices over 1000 euros from the last 30 days"
Output: [INV/2025/001, INV/2025/003, INV/2025/005] - Automatically found!
```

## What Is This?

**Ovunque** is an Odoo module that converts natural language questions into Odoo database queries using OpenAI's GPT-4. No SQL knowledge required. Ask in Italian, English, or a mix—the AI understands.

### Key Features

✅ **Natural Language Processing**: Write queries like "clienti da Milano" instead of technical domain syntax  
✅ **Multi-Language**: Works in Italian, English, and can be extended to other languages  
✅ **Wide Model Support**: Search across 9 major Odoo models (Partners, Invoices, Products, Orders, etc.)  
✅ **Smart Error Recovery**: Auto-fixes common LLM mistakes (price field confusion, computed fields, etc.)  
✅ **Debug Tools**: Built-in endpoints to inspect model fields and diagnose issues  
✅ **Query Audit Trail**: Every search is stored with its generated domain for transparency  

---

## Installation

### Prerequisites

- **Odoo**: 19.0 or later
- **Python**: 3.10+
- **OpenAI API Key**: Get one free at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (paid API calls)

### Option 1: Standard Installation

```bash
# 1. Copy module to Odoo addons directory
cp -r addons/ovunque /path/to/your/odoo/addons/

# 2. Install Python dependencies
pip install -r /path/to/your/odoo/addons/ovunque/requirements.txt

# 3. Restart Odoo
./odoo-bin -u all

# 4. Log in to Odoo and install "Ovunque" module via Apps menu
```

### Option 2: Docker Installation

```bash
# 1. Build and start containers
docker-compose up --build -d

# 2. Wait 15 seconds for Odoo to start

# 3. Install openai package in the container
docker exec -u odoo odoo-ai-19 pip install --user --break-system-packages 'openai>=1.0.0'

# 4. Restart container
docker restart odoo-ai-19

# 5. Visit http://localhost:8069 and install "Ovunque" module
```

If you see `Impossibile installare il modulo "ovunque" perché manca una dipendenza esterna: openai`, repeat step 3 and restart.

---

## Configuration

### Setting Up OpenAI API Key

#### Method 1: Via Odoo UI

1. Go to **Ovunque → Configuration → API Settings**
2. Create a new parameter:
   - **Key**: `ovunque.openai_api_key`
   - **Value**: `sk-...` (your API key from openai.com)

#### Method 2: Via Python Shell

```python
env['ir.config_parameter'].sudo().set_param('ovunque.openai_api_key', 'sk-your-key')
```

#### Method 3: Via Environment File

Create `.env` in the Ovunque directory:
```
OPENAI_API_KEY=sk-proj-abc123...
```

---

## How to Use

### Basic Search

1. Go to **Ovunque → Query Search** in the Odoo menu
2. Select a **Category**:
   - Clienti / Contatti (Customers/Contacts)
   - Prodotti (Products)
   - Fatture e Documenti (Invoices & Bills)
   - Ordini (Orders)
   - CRM / Opportunità (Leads & Opportunities)
   - Task Progetto (Project Tasks)
3. Type your query in natural language:
   - "Clienti da Milano"
   - "Fatture non pagate di gennaio 2025"
   - "Prodotti sotto 100 euro"
4. Click **Search**
5. Results appear in a table below

### Query Examples

#### Customers/Contacts (res.partner)
- "Clienti attivi" → Active customers
- "Fornitori da Milano" → Suppliers from Milan
- "Partner non contattati nel 2024" → Untouched partners in 2024

#### Invoices (account.move)
- "Fatture non pagate" → Unpaid invoices
- "Fatture di gennaio 2025" → January 2025 invoices
- "Documenti oltre 5000 euro" → Documents over 5000 euros

#### Products (product.template)
```
⚠️ IMPORTANT: Use "Prodotti" category for price searches!
```
- "Prodotti sotto 100 euro" → Products under 100 euros (uses list_price - selling price)
- "Articoli con costo superiore a 50" → Products with internal cost > 50
- "Prodotti attivi" → Active products
- "Basso stock sotto 10" → Low stock items

#### Orders (sale.order / purchase.order)
- "Ordini della scorsa settimana" → Last week's orders
- "Vendite sopra i 500 euro" → Sales over 500 euros
- "Acquisti confermati di novembre" → November purchases

---

## How It Works Internally

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. USER INPUT                                                     │
│    "Fatture non pagate di gennaio 2025"                          │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ 2. CATEGORY SELECTION                                            │
│    Category: "invoices" → Model: account.move                   │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ 3. BUILD INTELLIGENT PROMPT                                      │
│    • Model description                                           │
│    • All available stored fields                                 │
│    • Query examples for this model                               │
│    • Detailed rules for domain generation                        │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ 4. SEND TO GPT-4 API                                            │
│    ⏱ ~2-3 seconds average response time                         │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ 5. PARSE & VALIDATE RESPONSE                                     │
│    • Extract domain from markdown                                │
│    • Parse Python list syntax                                    │
│    • Auto-fix price field confusion                              │
│    • Validate all fields exist                                   │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ 6. EXECUTE SEARCH                                                │
│    Model.search([('state', '!=', 'posted'),                     │
│                  ('invoice_date', '>=', '2025-01-01'),          │
│                  ('invoice_date', '<', '2025-02-01')])          │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ 7. DISPLAY RESULTS                                               │
│    INV/2025/001, INV/2025/003, INV/2025/005                    │
│    (3 results found)                                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## Supported Models

| Model | Description | Example Queries |
|-------|-------------|-----------------|
| `res.partner` | Contacts/Customers/Suppliers | "Clienti attivi", "Fornitori da Milano" |
| `account.move` | Invoices & Bills | "Fatture non pagate", "Documenti oltre 5000" |
| `product.template` | Products (prices, costs) | "Prodotti sotto 100€", "Articoli attivi" |
| `product.product` | Product Variants (SKU specific) | "Varianti con barcode", "SKU attivi" |
| `sale.order` | Sales Orders | "Ordini della scorsa settimana" |
| `purchase.order` | Purchase Orders | "Acquisti confermati" |
| `stock.move` | Inventory Movements | "Movimenti in corso" |
| `crm.lead` | CRM Leads/Opportunities | "Deal vinti", "Opportunità aperte" |
| `project.task` | Project Tasks | "Task completati", "Task in progress" |

### ⚠️ Important: Product Price Searches

- **Use `product.template`** when searching by price
- **Use `product.product`** only for variants with barcode/SKU info
- `product.template` contains `list_price` (selling price) and `standard_price` (internal cost)
- `product.product` contains variant-specific data only (barcode, combination)

---

## API Reference

### POST /ovunque/search
Execute a natural language search.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "query": "unpaid invoices over 1000",
    "category": "invoices"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "results": [
      {"id": 1, "display_name": "INV/2025/001"},
      {"id": 2, "display_name": "INV/2025/002"}
    ],
    "count": 2,
    "domain": "[('state', '!=', 'posted'), ('amount_total', '>', 1000)]",
    "query_id": 42
  }
}
```

### GET /ovunque/models
List all available categories and models.

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "categories": [
      {"code": "customers", "label": "Clienti / Contatti"},
      {"code": "products", "label": "Prodotti"}
    ],
    "models": [
      {"name": "res.partner", "label": "Partner / Contact"},
      {"name": "account.move", "label": "Invoice"}
    ]
  }
}
```

### GET /ovunque/debug-fields?model=MODEL_NAME
Inspect stored vs computed fields for debugging.

**Usage:**
```
http://localhost:8069/ovunque/debug-fields?model=res.partner
http://localhost:8069/ovunque/debug-fields?model=product.template
```

Returns an HTML page with two tables:
- **Green section**: Stored fields (can be used in queries)
- **Orange section**: Computed fields (cannot be used)

---

## Troubleshooting & Debugging

### Problem: Empty Results `[]`

When your query returns `[]` (no results), it usually means the LLM didn't generate a valid domain.

**Debug Steps:**

1. **Check the Raw LLM Response**:
   - Go to **Ovunque → Query Search**
   - Click on the problematic query
   - Scroll to **Debug Info** tab
   - Read the **Raw LLM Response** field

2. **Analyze the response**:
   - If it shows `[]` → LLM didn't understand the query
   - If it shows long text → Response parsing failed
   - If it shows code with errors → Syntax error in domain

3. **Check logs** (in development):
   ```bash
   tail -f /var/log/odoo/odoo.log | grep -E "\[LLM\]|\[PARSE\]|\[REPAIR\]"
   ```

### Problem: "Field X is computed and cannot be used in queries"

The LLM tried to use a computed field (like `lst_price` instead of `list_price`).

**Root Cause**: Field names are similar but computed fields aren't in the database.

**Solutions**:

1. **Reload the module** (cache issue):
   - Go to **Apps → Ovunque → Click reload button**

2. **Check available fields**:
   - Visit: `http://localhost:8069/ovunque/debug-fields?model=product.template`
   - Look for the field name in the green table

3. **Rephrase your query** more specifically:
   - ✗ "Articoli sotto i 100€"
   - ✓ "Prodotti con list_price sotto 100"

4. **For price queries**, always verify you're using the right category:
   - Use "**Prodotti**" category for price searches
   - This auto-selects `product.template` which has prices
   - Don't use "Product Variant" category for price searches

### Problem: "OpenAI API key not configured"

You haven't set up the API key yet.

**Solution**:

1. **Via Odoo UI**:
   - Settings → Ovunque → API Settings
   - Add parameter: `ovunque.openai_api_key` = `sk-...`

2. **Via shell**:
   ```python
   env['ir.config_parameter'].sudo().set_param('ovunque.openai_api_key', 'sk-...')
   ```

3. **Get API key from**: https://platform.openai.com/api-keys

### Problem: "Connection error with OpenAI"

Network issue or API down.

**Solutions**:
- Check internet connection
- Check API key is valid at https://platform.openai.com/account/api-keys
- Verify account has credits (check https://platform.openai.com/account/billing/overview)
- Try again in a few seconds

### Problem: "Rate limits exceeded"

You've made too many API calls too quickly.

**Solution**: Wait a few minutes and try again. Consider:
- Using specific category selections instead of broad searches
- Breaking complex queries into multiple smaller searches
- Checking OpenAI pricing to understand your quota

---

## Advanced Debugging

### Using the Debug Fields Tool

View all available fields for a model:

```bash
# In Odoo shell
./odoo-bin shell

# Then execute:
exec(open('/path/to/addons/ovunque/debug_fields.py').read())
```

Output shows:
```
========================================
Model: res.partner
Total stored fields: 50
========================================
  • id                             (integer  ) - ID
  • name                           (char     ) - Name
  • active                         (boolean  ) - Active
  • email                          (char     ) - Email
  • phone                          (char     ) - Phone
  • city                           (char     ) - City
  • state_id                       (many2one ) - State
  [... and more ...]
```

### Checking Prompt Construction

The prompt sent to GPT-4 includes:
1. Model description
2. List of all available stored fields (max 50)
3. Model-specific examples
4. Detailed rules for domain generation
5. Your query

To verify the prompt is correct, check the logs with filter `[LLM]`.

### Understanding Log Prefixes

```
[LLM]    - Communicating with OpenAI API
[PARSE]  - Parsing response into Python list
[REPAIR] - Attempting to fix syntax errors
[VALIDATE] - Checking fields exist in model
[FIX]    - Auto-fixing field names (e.g., price fields)
[CHECK]  - Verifying model is installed
[SELECT] - Category → Model selection
[ERROR]  - Something went wrong
```

---

## Database Schema

### search.query

Stores each natural language query and its results.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Natural language query text |
| `category` | Selection | Category chosen (customers, products, etc.) |
| `model_name` | Char | Actual Odoo model (res.partner, account.move) |
| `model_domain` | Text | Generated domain: `[('field', 'op', value)]` |
| `raw_response` | Text | Raw response from OpenAI (for debugging) |
| `results_count` | Integer | Number of results returned |
| `status` | Selection | draft / success / error |
| `error_message` | Text | Error description if status=error |
| `result_ids` | One2many | Linked search.result records |
| `created_by_user` | Many2one | User who created the query |

### search.result

Individual results from a search query.

| Field | Type | Description |
|-------|------|-------------|
| `query_id` | Many2one | Reference to parent search.query |
| `record_id` | Integer | ID of found record |
| `record_name` | Char | Display name of record |
| `model` | Char | Model name (e.g., "res.partner") |

---

## Permissions

Two access levels are implemented (see `security/ir.model.access.csv`):

- **User Level**: Can create, read, modify queries; read results
- **Manager Level**: Full access including delete

---

## Limitations

⚠️ **Know Before You Use**

- **Max 50 results per query** (configurable in code)
- **Only standard Odoo models** supported (custom models need manual configuration)
- **Requires paid OpenAI API** (GPT-4 is not free, but cheap ~0.03¢ per query)
- **No JOINs between models** (single-model searches only)
- **Language**: Italian/English (easily extended to other languages)
- **LLM Hallucinations**: Occasionally generates slightly wrong domains (we auto-fix common ones)

---

## Project Structure

```
ai-odoo-data-assistant/
├── addons/
│   └── ovunque/                    # Main Odoo module
│       ├── __manifest__.py         # Module metadata & dependencies
│       ├── __init__.py             # Imports models & controllers
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   └── search_query.py    # Core business logic
│       │                           # - SearchQuery model
│       │                           # - SearchResult model
│       │                           # - LLM integration
│       │                           # - Domain parsing & validation
│       │
│       ├── controllers/
│       │   ├── __init__.py
│       │   └── search_controller.py # REST API endpoints
│       │                            # - /ovunque/search (main search)
│       │                            # - /ovunque/models (list categories)
│       │                            # - /ovunque/debug-fields (field inspector)
│       │
│       ├── views/
│       │   ├── search_query_views.xml # UI forms & lists
│       │   └── menu.xml               # Odoo menu configuration
│       │
│       ├── security/
│       │   └── ir.model.access.csv   # User/Manager permissions
│       │
│       ├── utils.py                  # Helper functions
│       │                             # - API key setup
│       │                             # - Field extraction for LLM
│       │                             # - Result parsing
│       │                             # - Domain validation
│       │
│       ├── debug_fields.py           # Shell script for field inspection
│       ├── requirements.txt          # Python dependencies (openai)
│       ├── config_example.py         # Configuration template
│       ├── .env.example              # Environment variables template
│       └── README.md                 # Module-specific documentation
│
├── docker-compose.yml               # Docker setup
├── odoo.conf                        # Odoo configuration
├── CLAUDE.md                        # Development notes & improvements log
└── README.md                        # This file
```

---

## Key Code Components

### SearchQuery Model (models/search_query.py)

**Main methods:**

- `action_execute_search()` - Entry point for search execution
- `_parse_natural_language()` - Calls OpenAI GPT-4 API
- `_build_prompt()` - Constructs detailed LLM prompt with field information
- `_parse_domain_response()` - Extracts domain from LLM response
- `_validate_domain_fields()` - Checks all fields exist in model
- `_fix_price_fields()` - Auto-fixes common price field mistakes
- `_get_model_examples()` - Model-specific query examples for LLM
- `_attempt_domain_repair()` - Tries to fix syntax errors in response

**Field mappings:**
- `category` (Selection) → Automatically selects model via CATEGORY_MODELS dict
- `model_name` (Selection) → Specific Odoo model to search
- `model_domain` (Text) → Generated domain stored as string
- `raw_response` (Text) → Full OpenAI response (for debugging)
- `status` (Selection) → draft / success / error

### SearchController (controllers/search_controller.py)

**REST API endpoints:**

- `POST /ovunque/search` - Main search endpoint
- `GET /ovunque/models` - List available categories & models
- `GET /ovunque/debug-fields` - HTML field inspector for debugging

### Utility Functions (utils.py)

- `setup_api_key()` - Configure OpenAI key in database
- `get_model_fields_for_llm()` - Extract fields for prompt building
- `parse_search_results()` - Convert recordset to API response format
- `validate_domain()` - Verify domain structure
- `common_search_patterns()` - Example queries by model

---

## Development Notes

### Adding Support for a New Model

1. Add model to `AVAILABLE_MODELS` in `SearchQuery` class
2. Add category mapping in `CATEGORY_MODELS` dictionary
3. Add model description in `_get_model_description()`
4. Add examples in `_get_model_examples()`
5. Add to `AVAILABLE_MODELS` list in `debug_fields.py`
6. Test with `/ovunque/debug-fields?model=your.model`

### Extending to Other Languages

1. The prompt in `_build_prompt()` can be translated
2. Update example queries in `_get_model_examples()` 
3. The UI translations go in views XML files
4. Add language-specific prompt templates

### Integrating Other LLMs

To use Claude, Ollama, or other LLMs instead of GPT-4:

1. Replace OpenAI client in `_parse_natural_language()`
2. Adjust system message and parameters for your LLM
3. Update imports and API key retrieval
4. Test with your LLM's temperature/token settings

---

## Performance & Costs

### API Costs (Approximate)

GPT-4 pricing varies, but typically:
- **~0.01¢ - 0.05¢ per query** depending on complexity
- **1000 queries ≈ $0.50 - $2.00**

To minimize costs:
- Cache repeated searches locally
- Batch simple queries together
- Use specific categories to reduce token usage

### Response Time

- **Average**: 2-3 seconds
- **Fast queries**: 1-2 seconds
- **Complex queries**: 3-5 seconds

Mostly depends on OpenAI API load and network latency.

---

## Contributing

Contributions are welcome! Areas for improvement:

- [ ] Add support for more models
- [ ] Improve LLM prompt engineering
- [ ] Add caching layer for repeated queries
- [ ] Create UI wizard for complex multi-model searches
- [ ] Add query suggestion/autocomplete
- [ ] Support for more LLMs (Claude, Ollama, local models)
- [ ] Better error messages in Italian
- [ ] Query history and favorites

---

## License

AGPL-3.0

---

## Support & Documentation

- **Module README**: `addons/ovunque/README.md`
- **Development Guide**: `addons/ovunque/DEVELOPMENT.md`
- **Debug Guide**: `CLAUDE.md`
- **Issues**: Check the repository issues tracker
- **API Examples**: See controllers/search_controller.py for endpoint details

---

## Changelog

### v19.0.1.0.0 (Current)

- ✅ Initial release with GPT-4 integration
- ✅ Support for 9 major Odoo models
- ✅ Auto-fix for price field confusion
- ✅ Detailed error messages with suggestions
- ✅ Debug tools for field inspection
- ✅ Full API documentation
- ✅ Docker support
- ✅ Comprehensive code comments
