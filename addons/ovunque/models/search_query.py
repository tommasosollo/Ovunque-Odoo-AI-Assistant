import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    _logger.warning("openai library not installed")


class SearchQuery(models.Model):
    """
    Natural Language Search Query Model
    
    This model represents a single user query written in natural language.
    The model:
    1. Accepts user input in Italian/English (e.g., "unpaid invoices")
    2. Uses OpenAI GPT-4 to convert the query to an Odoo domain
    3. Executes the domain search on the selected model
    4. Stores results for user review
    
    Key Methods:
    - action_execute_search(): Main entry point for processing queries
    - _parse_natural_language(): Communicates with OpenAI API
    - _build_prompt(): Constructs detailed prompt with model information
    - _parse_domain_response(): Extracts and validates the domain from LLM response
    """
    _name = 'search.query'
    _description = 'Natural Language Search Query'
    _order = 'create_date desc'

    # List of all Odoo models that can be searched through this interface
    AVAILABLE_MODELS = [
        ('res.partner', 'Partner / Contact'),
        ('account.move', 'Invoice'),
        ('product.product', 'Product Variant'),
        ('product.template', 'Product Template'),
        ('sale.order', 'Sales Order'),
        ('purchase.order', 'Purchase Order'),
        ('stock.move', 'Stock Move'),
        ('crm.lead', 'CRM Lead'),
        ('project.task', 'Project Task'),
    ]
    
    # Maps user-friendly categories to their corresponding Odoo models
    # This allows users to select "Clienti" and the system auto-selects res.partner
    CATEGORY_MODELS = {
        'customers': ['res.partner'],
        'suppliers': ['res.partner'],
        'partners': ['res.partner'],
        'invoices': ['account.move'],
        'bills': ['account.move'],
        'documents': ['account.move'],
        'products': ['product.template', 'product.product'],
        'inventory': ['stock.move', 'product.template'],
        'orders': ['sale.order', 'purchase.order'],
        'sales': ['sale.order'],
        'purchases': ['purchase.order'],
        'crm': ['crm.lead'],
        'opportunities': ['crm.lead'],
        'tasks': ['project.task'],
        'projects': ['project.task'],
    }

    # The natural language query text entered by the user (e.g., "unpaid invoices over 1000")
    name = fields.Char('Query Text', required=True)
    
    # User-friendly category selection (Clienti, Prodotti, etc.)
    # Based on this, the system auto-selects the appropriate Odoo model from CATEGORY_MODELS
    category = fields.Selection([
        ('customers', 'Clienti / Contatti'),
        ('products', 'Prodotti'),
        ('invoices', 'Fatture e Documenti'),
        ('orders', 'Ordini'),
        ('crm', 'CRM / Opportunità'),
        ('tasks', 'Task Progetto'),
    ], 'Categoria', required=True, default='customers')
    
    # Specific Odoo model selected after category is processed (res.partner, account.move, etc.)
    # Set automatically by action_execute_search() based on the category
    model_name = fields.Selection(AVAILABLE_MODELS, 'Modello Specifico', readonly=True)
    
    # Generated Odoo domain as a string (e.g., "[('state', '=', 'draft')]")
    # Produced by GPT-4 and stored for debugging/auditing purposes
    model_domain = fields.Text('Generated Domain')
    
    # Count of results returned by the search query
    results_count = fields.Integer('Results Count')
    
    # Raw response text from OpenAI API (stored for debugging)
    # Helpful for troubleshooting when the LLM doesn't generate valid domains
    raw_response = fields.Text('Raw LLM Response')
    
    # One2many relationship to SearchResult records
    # Contains all the records found by the search domain
    result_ids = fields.One2many('search.result', 'query_id', 'Results')
    
    # Status of the query: 'draft' = initial, 'success' = completed, 'error' = failed
    status = fields.Selection([
        ('draft', 'Draft'),
        ('success', 'Success'),
        ('error', 'Error'),
    ], default='draft')
    
    # Error message in case of failures (API key missing, invalid domain, etc.)
    error_message = fields.Text('Error Message')
    
    # Reference to the user who created this query
    created_by_user = fields.Many2one('res.users', 'Created By', default=lambda self: self.env.user)

    def action_execute_search(self):
        """
        Main execution method for natural language search.
        
        Flow:
        1. Delete any previous results for this query
        2. Validate that a category was selected
        3. Select the appropriate Odoo model based on category
        4. Parse natural language to Odoo domain using LLM
        5. Execute the domain search
        6. Store results in search.result records
        7. Update status (success/error) and error messages
        """
        for record in self:
            try:
                record.result_ids.unlink()
                
                if not record.category:
                    raise UserError(_('Please select a category (Clienti, Prodotti, etc.) before searching.'))
                
                available_models = self.CATEGORY_MODELS.get(record.category, ['res.partner'])
                
                valid_model = None
                for model in available_models:
                    try:
                        self.env[model]
                        valid_model = model
                        break
                    except KeyError:
                        _logger.warning(f"[CHECK] Model {model} not installed")
                        continue
                
                if not valid_model:
                    category_label = dict(record._fields['category'].selection).get(record.category, record.category)
                    error_msg = _(
                        'The required module for "%s" is not installed.\n\n'
                        'To enable this feature:\n'
                        '1. Go to Apps in Odoo\n'
                        '2. Search for the module (e.g., "CRM", "Sales", "Inventory")\n'
                        '3. Click "Install"\n'
                        '4. Come back and try again\n\n'
                        'Technical: Missing modules: %s'
                    ) % (category_label, ', '.join(available_models))
                    raise UserError(error_msg)
                
                record.model_name = valid_model
                _logger.warning(f"[SELECT] Category {record.category} → Model {valid_model}")
                
                domain = record._parse_natural_language()
                record.model_domain = str(domain)
                record.status = 'success'
                
                Model = self.env[record.model_name]
                results = Model.search(domain)
                record.results_count = len(results)
                
                result_data = []
                for res in results:
                    result_data.append((0, 0, {
                        'record_id': res.id,
                        'record_name': res.display_name,
                        'model': record.model_name,
                    }))
                record.result_ids = result_data
            except Exception as e:
                record.status = 'error'
                record.error_message = str(e)
                _logger.error(f"Error executing search: {e}")

    def _parse_natural_language(self):
        """
        Convert natural language query to Odoo domain using OpenAI GPT-4.
        
        Process:
        1. Retrieve OpenAI API key from Odoo configuration
        2. Get all stored fields for the selected model
        3. Build a detailed prompt with field information and examples
        4. Send prompt to GPT-4 API with system message about domain generation
        5. Parse the response to extract the domain list
        6. Validate the domain against the model's fields
        7. Return the parsed domain for database search
        
        Returns:
            list: Odoo domain (list of tuples) to be used in Model.search()
            
        Raises:
            UserError: If API key missing, model not installed, parsing fails, etc.
        """
        api_key = self.env['ir.config_parameter'].sudo().get_param('ovunque.openai_api_key')
        
        if not api_key:
            raise UserError(_(
                'OpenAI API key is not configured.\n\n'
                'To fix this:\n'
                '1. Go to Settings → Ovunque → API Settings\n'
                '2. Get your API key from openai.com/api/keys\n'
                '3. Paste the key (starts with "sk-")\n'
                '4. Save and try again\n\n'
                'Need help? Check the documentation in the module.'
            ))
        
        try:
            _logger.warning(f"[LLM] Starting query parsing for: {self.name}")
            _logger.warning(f"[LLM] Model name: {self.model_name}")
            
            if not self.model_name:
                raise UserError(_('No model selected. Please select a category.'))
            
            try:
                Model = self.env[self.model_name]
            except KeyError:
                raise UserError(_(
                    'The module for "%s" is not installed.\n\n'
                    'Please install the required module in Odoo:\n'
                    '1. Go to Apps\n'
                    '2. Search for "crm", "Sale", "Purchase", etc.\n'
                    '3. Click Install\n\n'
                    'Then come back and try again.'
                ) % self.model_name)
            
            model_fields = Model.fields_get()
            client = OpenAI(api_key=api_key)
            
            _logger.warning(f"[LLM] Model: {self.model_name}, Available fields: {len(model_fields)}")
            
            prompt = self._build_prompt(model_fields)
            _logger.warning(f"[LLM] Prompt length: {len(prompt)} chars")
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an Odoo domain filter generator. Convert natural language queries to Odoo domain syntax (Python list of tuples). Respond ONLY with valid Python list syntax. No explanations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content.strip()
            self.raw_response = response_text
            _logger.warning(f"[LLM] Response received: {response_text[:300]}")
            
            domain = self._parse_domain_response(response_text)
            return domain
            
        except UserError:
            raise
        except Exception as e:
            error_str = str(e).lower()
            _logger.error(f"[LLM ERROR] LLM parsing error: {str(e)}")
            
            if 'timeout' in error_str or 'connection' in error_str:
                raise UserError(_('Connection error with OpenAI. Please check your internet connection and try again.'))
            elif 'authentication' in error_str or 'invalid' in error_str or 'api' in error_str:
                raise UserError(_('OpenAI API key error. Please verify your API key in Settings → Ovunque → API Settings.'))
            elif 'rate' in error_str:
                raise UserError(_('You have exceeded OpenAI API rate limits. Please wait a few minutes and try again.'))
            else:
                raise UserError(_('Error communicating with OpenAI: %s\n\nPlease check Settings → Ovunque → API Settings.') % str(e)[:100])

    def _build_prompt(self, model_fields):
        """
        Build a detailed prompt for GPT-4 that includes:
        - Model information and description
        - All available database fields (stored only, no computed fields)
        - Examples specific to this model type
        - Clear rules for domain generation
        - The user's natural language query
        
        The prompt is designed to minimize hallucination and encourage
        GPT-4 to generate valid Odoo domains.
        
        Args:
            model_fields: Dictionary of fields from Model.fields_get()
            
        Returns:
            str: Complete prompt ready for GPT-4 API call
        """
        fields_info = self._get_field_info(model_fields)
        model_examples = self._get_model_examples()
        
        prompt = f"""TASK: Convert natural language query to Odoo domain (Python list of tuples).
RESPOND WITH ONLY THE DOMAIN LIST. NO EXPLANATIONS, NO MARKDOWN.

===== MODEL INFORMATION =====
Model: {self.model_name}
Description: {self._get_model_description()}

===== AVAILABLE FIELDS (DATABASE STORED ONLY - USE ONLY THESE) =====
{fields_info}

===== FIELD EXAMPLES FOR THIS MODEL =====
{model_examples}

===== RULES (CRITICAL - YOU MUST FOLLOW) =====
1. RESPOND WITH ONLY A PYTHON LIST: [(...), (...)]
2. EVERY field name must EXACTLY match one from the list above
3. Do NOT invent field names, do NOT use variations
4. Do NOT use computed fields (they are NOT in the list)
5. Operators: '=', '!=', '>', '<', '>=', '<=', 'ilike', 'like', 'in', 'not in'
6. Dates: YYYY-MM-DD format, e.g. '2025-01-15'
7. Numbers: plain integers/floats, NO currency symbols (100, not 100€)
8. Booleans: True/False (no quotes)
9. Many2one: use ('field.name', 'operator', 'text') OR ('field_id', '=', number)
10. SPECIAL: For product models, see the specific field mapping rules above (especially price fields)
11. IF you cannot safely create a domain → respond with: []

===== VALID RESPONSE EXAMPLES =====
[('state', '=', 'confirmed')]
[('name', 'ilike', 'test'), ('active', '=', True)]
[('date_start', '>=', '2025-01-01')]
[('price_total', '>', 1000)]
[]

===== YOUR TASK =====
Query: "{self.name}"
Response (ONLY the list, nothing else):"""
        return prompt

    def _get_field_info(self, model_fields):
        """
        Extract stored (non-computed) fields from the model and format them for LLM.
        
        This method filters out:
        - Private fields (starting with _)
        - Computed fields (store=False)
        
        These restrictions ensure GPT-4 only sees fields that can be used in domain queries.
        
        Args:
            model_fields: Dictionary from Model.fields_get()
            
        Returns:
            str: Formatted field list, max 50 fields (first 50 chars per line)
        """
        fields_info = []
        for field_name, field_data in model_fields.items():
            if field_name.startswith('_'):
                continue
            
            is_stored = field_data.get('store', True) is not False
            if not is_stored:
                continue
            
            field_type = field_data.get('type', 'unknown')
            field_string = field_data.get('string', field_name)
            fields_info.append(f"- {field_name} ({field_type}): {field_string}")
        
        return "\n".join(fields_info[:50])
    
    def _get_model_description(self):
        """
        Get a human-readable English description of what each model represents.
        
        These descriptions are included in the LLM prompt to give GPT-4 context
        about the model structure and purpose.
        
        Returns:
            str: Description of the model (e.g., "Contacts, Customers, Suppliers, Companies")
        """
        descriptions = {
            'res.partner': 'Contacts, Customers, Suppliers, Companies',
            'account.move': 'Invoices and Bills (posted documents)',
            'product.product': 'Product Variants (specific SKUs with combinations)',
            'product.template': 'Product Templates (prices, costs, inventory by template)',
            'sale.order': 'Sales Orders',
            'purchase.order': 'Purchase Orders',
            'stock.move': 'Stock Movements and Inventory',
            'crm.lead': 'CRM Leads and Opportunities',
            'project.task': 'Project Tasks and Work Items',
        }
        return descriptions.get(self.model_name, self.model_name)
    
    def _get_model_examples(self):
        """
        Provide model-specific examples in the LLM prompt.
        
        Each model has its own set of real-world query examples that show GPT-4:
        - What queries are typical for this model
        - How natural language maps to domain syntax
        - Special cases (e.g., price vs cost for products)
        
        These examples significantly improve the accuracy of generated domains.
        
        Returns:
            str: Formatted examples for the current model
        """
        examples = {
            'res.partner': """
- "Customers from Milan" → [('city', 'ilike', 'Milan'), ('customer_rank', '>', 0)]
- "Suppliers" → [('supplier_rank', '>', 0)]
- "Active contacts" → [('active', '=', True)]
- "Inactive partners" → [('active', '=', False)]""",
            'account.move': """
- "Unpaid invoices" → [('state', '!=', 'posted'), ('payment_state', '=', 'not_paid')]
- "Invoices from January 2025" → [('invoice_date', '>=', '2025-01-01'), ('invoice_date', '<', '2025-02-01')]
- "Large invoices over 1000" → [('amount_total', '>', 1000)]""",
            'product.product': """
- "Variants with barcode starting with 123" → [('barcode', 'like', '123')]
- "Active variants" → [('active', '=', True)]
- "Variants with default_code starting with SKU" → [('default_code', 'like', 'SKU')]
NOTE: For price/cost queries, use product.template model instead (prices are stored there)""",
            'product.template': """
IMPORTANT PRICE DISTINCTION:
- list_price = SELLING PRICE (what customer pays) - for queries about "price", "prezzo", "cost to customer"
- standard_price = INTERNAL COST (our cost) - only for "internal cost", "costo interno", "cost price"

EXAMPLES:
- "Products under 100 euros" → [('list_price', '<', 100)]
- "Articles cheaper than 50" → [('list_price', '<', 50)]
- "Products with selling price under 100" → [('list_price', '<', 100)]
- "Products with internal cost > 50" → [('standard_price', '>', 50)]
- "Products with our cost above 100" → [('standard_price', '>', 100)]
- "Active products" → [('active', '=', True)]
- "Low stock products" → [('qty_available', '<', 10), ('active', '=', True)]
- "Electronics products" → [('categ_id.name', 'ilike', 'Electronics')]

KEY RULE: If user mentions "price", "prezzo", "euro", "cost to customer" → ALWAYS use list_price
KEY RULE: If user specifically mentions "internal cost", "costo interno", "our cost", "cost price" → use standard_price""",
            'sale.order': """
- "Draft orders" → [('state', '=', 'draft')]
- "Confirmed sales from last month" → [('state', '=', 'sale')]
- "Orders over 500" → [('amount_total', '>', 500)]""",
            'purchase.order': """
- "RFQ pending" → [('state', '=', 'draft')]
- "Confirmed purchases" → [('state', 'in', ['purchase', 'done'])]""",
            'stock.move': """
- "In progress moves" → [('state', '=', 'confirmed')]
- "Done moves" → [('state', '=', 'done')]""",
            'crm.lead': """
- "Open opportunities" → [('probability', '>', 0), ('probability', '<', 100)]
- "Lost deals" → [('probability', '=', 0)]
- "Won deals" → [('probability', '=', 100)]""",
            'project.task': """
- "Open tasks" → [('state', 'in', ['todo', 'in_progress'])]
- "Completed tasks" → [('state', '=', 'done')]""",
        }
        return examples.get(self.model_name, "No specific examples available")

    def _parse_domain_response(self, response_text):
        """
        Extract and validate the Odoo domain from GPT-4 response.
        
        Process:
        1. Remove markdown formatting (```, code fences)
        2. Extract the list using regex
        3. Parse using ast.literal_eval (safe)
        4. If parsing fails, attempt repair with fallback strategies
        5. Fix price field issues automatically
        6. Validate all fields exist in the model
        
        Args:
            response_text: Raw text response from GPT-4 API
            
        Returns:
            list: Parsed and validated Odoo domain
            
        Raises:
            UserError: If domain cannot be parsed or validated
        """
        import re
        import ast
        try:
            cleaned = response_text.strip()
            _logger.warning(f"[PARSE] Original response (first 500 chars): {cleaned[:500]}")
            
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```python\n?', '', cleaned)
                cleaned = re.sub(r'^```\n?', '', cleaned)
                cleaned = re.sub(r'```.*$', '', cleaned, flags=re.DOTALL).strip()
                _logger.warning(f"[PARSE] After removing markdown: {cleaned[:500]}")
            
            match = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(0)
                _logger.warning(f"[PARSE] Extracted list: {cleaned[:500]}")
            else:
                _logger.warning(f"[PARSE] No list found in response. Full response: {cleaned[:500]}")
            
            if not cleaned or cleaned == '[]':
                _logger.warning(f"[PARSE] Empty domain returned (query: {self.name})")
                return []
            
            try:
                domain = ast.literal_eval(cleaned)
            except (ValueError, SyntaxError) as e:
                _logger.warning(f"[PARSE] ast.literal_eval failed ({e}), attempting fallback repairs...")
                domain = self._attempt_domain_repair(cleaned)
            
            if not isinstance(domain, list):
                raise ValueError(f"Response is not a list: {type(domain)}")
            
            domain = self._fix_price_fields(domain)
            self._validate_domain_fields(domain)
            _logger.warning(f"[PARSE] Successfully parsed domain: {domain}")
            return domain
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"[PARSE ERROR] Domain parsing failed: {str(e)}. Query: '{self.name}'. Raw response (first 300 chars): {response_text[:300]}")
            raise UserError(_(
                'The AI could not understand your search.\n\n'
                'Try:\n'
                '• Using simpler words\n'
                '• Being more specific (e.g., "invoices from January" instead of "old invoices")\n'
                '• Checking the category selection matches your query\n\n'
                'Error: %s'
            ) % str(e)[:80])
    
    def _validate_domain_fields(self, domain):
        """
        Validate that all fields referenced in the domain exist and are stored (not computed).
        
        This prevents errors like:
        - Using a field that doesn't exist: Field "typo_name" does not exist
        - Using a computed field: Field "lst_price" is computed (not in database)
        
        For dot-notation fields (e.g., 'partner_id.name'), only checks the base field.
        
        Args:
            domain: List of tuples representing the Odoo domain
            
        Raises:
            UserError: If any field is invalid or computed
        """
        if not domain:
            return
        
        Model = self.env[self.model_name]
        model_fields = Model.fields_get()
        
        for clause in domain:
            if not isinstance(clause, (tuple, list)) or len(clause) < 3:
                continue
            
            field_name = clause[0]
            
            if field_name in ('|', '&', '!'):
                continue
            
            base_field = field_name.split('.')[0]
            
            if base_field not in model_fields:
                stored_fields = self._get_available_stored_fields()
                error_msg = _(
                    'The field "%s" does not exist in this module.\n\n'
                    'AI may have misunderstood your query.\n\n'
                    'Available fields:\n%s\n\n'
                    'Try rephrasing your question or check the Debug Info tab for details.'
                ) % (base_field, stored_fields[:200])
                raise UserError(error_msg)
            
            field_data = model_fields[base_field]
            if field_data.get('store') is False:
                stored_fields = self._get_available_stored_fields()
                error_msg = _(
                    'The field "%s" is calculated, not stored in database.\n\n'
                    'This is a limitation of Odoo - use stored fields instead.\n\n'
                    'Try a different search or use one of these fields:\n%s'
                ) % (base_field, stored_fields[:200])
                raise UserError(error_msg)
            
            _logger.warning(f"[VALIDATE] Field '{base_field}' is valid and stored")
    
    def _fix_price_fields(self, domain):
        """
        Auto-fix common LLM mistakes with price field confusion.
        
        Common mistakes GPT-4 makes:
        1. Using 'standard_price' (internal cost) when user asks for "price" (selling price)
        2. Trying to use 'list_price' on product.product (prices are on product.template)
        
        This method intelligently detects these mistakes by analyzing:
        - Keywords in the user's query (prezzo, price, euro, cost, etc.)
        - The model being searched
        - The field being used
        
        Args:
            domain: List of tuples to fix
            
        Returns:
            list: Fixed domain with corrected price field references
            
        Raises:
            UserError: If price query on product.product (wrong model)
        """
        if not domain or self.model_name not in ('product.template', 'product.product'):
            return domain
        
        query_lower = self.name.lower()
        has_price_keywords = any(word in query_lower for word in ['prezzo', 'price', 'euro', '€', 'under', 'sopra', 'above', 'below', 'less', 'more', 'cheaper', 'expensive'])
        has_cost_keywords = any(word in query_lower for word in ['costo interno', 'internal cost', 'cost price', 'nostra cost', 'our cost'])
        
        for i, clause in enumerate(domain):
            if not isinstance(clause, (tuple, list)) or len(clause) < 3:
                continue
            
            field_name = clause[0]
            operator = clause[1]
            value = clause[2]
            
            if field_name == 'standard_price' and self.model_name == 'product.template':
                if has_price_keywords and not has_cost_keywords:
                    _logger.warning(f"[FIX] Query '{self.name}' on template uses standard_price, but looks like a selling price query. Changing to list_price")
                    domain[i] = ('list_price', operator, value)
            
            elif field_name == 'list_price' and self.model_name == 'product.product':
                error_msg = _(
                    'Price search not available for Product Variants.\n\n'
                    'Solution: Change the category to "Prodotti" (Products)\n'
                    'The system will automatically select the right model.\n\n'
                    'Technical info:\n'
                    '• Product Templates: have prices (list_price, standard_price)\n'
                    '• Product Variants: have SKU/barcode info only'
                )
                raise UserError(error_msg)
        
        return domain
    
    def _get_available_stored_fields(self):
        """
        Get a list of stored field names from the model for error messages.
        
        Used when displaying which fields are available to the user if they
        get an error about an invalid field name.
        
        Returns:
            str: Comma-separated list of up to 20 stored field names
        """
        Model = self.env[self.model_name]
        model_fields = Model.fields_get()
        
        stored = []
        for field_name, field_data in model_fields.items():
            if field_name.startswith('_'):
                continue
            if field_data.get('store') is not False:
                stored.append(field_name)
        
        return ', '.join(sorted(stored)[:20])
    
    def _attempt_domain_repair(self, domain_str):
        """
        Attempt to fix common syntax errors in LLM-generated domain strings.
        
        Sometimes GPT-4 produces nearly-valid Python syntax with small issues:
        - Mixed quote styles ('\"text\")
        - Malformed boolean/None values
        
        This method tries:
        1. Common string replacements (quote fixes, boolean/None normalization)
        2. ast.literal_eval (safe, no code execution)
        3. eval as last resort (if literal_eval fails)
        4. Return empty domain [] if all repairs fail
        
        Args:
            domain_str: String that should be a Python list but has syntax errors
            
        Returns:
            list: Repaired domain, or [] if cannot be fixed
        """
        import ast
        repairs = [
            (r"'\"", "'"),
            (r"\"'", "'"),
            (r"True", "True"),
            (r"False", "False"),
            (r"None", "None"),
        ]
        
        for pattern, replacement in repairs:
            domain_str = domain_str.replace(pattern, replacement)
        
        try:
            return ast.literal_eval(domain_str)
        except:
            try:
                return eval(domain_str)
            except:
                _logger.error(f"[REPAIR] Failed to repair domain: {domain_str[:200]}")
                return []


class SearchResult(models.Model):
    """
    Search Query Result Model
    
    Represents a single result record returned by a natural language search.
    
    This model serves as a Many2one target for SearchQuery, allowing:
    - Easy access to results from the UI
    - Audit trail of what records were found
    - Support for large result sets (up to 50 results per query)
    
    Fields store the original record ID, display name, and model for reference,
    since we don't want to create foreign key constraints to arbitrary models.
    """
    _name = 'search.result'
    _description = 'Search Query Result'
    _order = 'id desc'

    # Many2one reference back to the SearchQuery that produced this result
    # Cascade delete ensures results are cleaned up when query is deleted
    query_id = fields.Many2one('search.query', 'Query', ondelete='cascade', required=True)
    
    # Integer ID of the found record (not a foreign key, can reference any model)
    record_id = fields.Integer('Record ID', required=True)
    
    # Display name of the found record (e.g., "Invoice INV/2025/001")
    record_name = fields.Char('Record Name', required=True)
    
    # Model name of the found record (e.g., "account.move", "res.partner")
    # Stored as string so we can reference any model type
    model = fields.Char('Model', required=True)
