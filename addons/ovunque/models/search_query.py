import logging
import json
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import Counter

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
    2. Uses OpenAI GPT-4 to convert the query to an Odoo domain or structured JSON spec
    3. Detects query type: simple domain vs. complex multi-model (count_aggregate, exclusion)
    4. Executes the appropriate search method (domain, structured aggregation, etc.)
    5. Stores results and execution metadata for user review and debugging
    
    Key Methods:
    - action_execute_search(): Main entry point for processing queries
    - _execute_single_model_search(): Handles both simple and structured queries
    - _parse_natural_language(): Communicates with OpenAI API for query parsing
    - _parse_query_response(): Intelligently detects response format (JSON vs domain)
    - _execute_structured_query(): Routes to count_aggregate or exclusion execution
    - _execute_count_aggregate_from_spec(): Counts related records with threshold filtering
    - _execute_exclusion_from_spec(): Finds records NOT present in related model
    - _build_prompt(): Constructs detailed prompt with model info and examples
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
    # Can be in Italian, English, or mixed
    name = fields.Char('Query Text', required=True)
    
    # User-friendly category selection (Clienti, Prodotti, etc.)
    # Based on this, the system auto-selects the appropriate Odoo model from CATEGORY_MODELS
    # Categories map to business domains to guide the LLM
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
    # Used for field introspection and ORM operations
    model_name = fields.Selection(AVAILABLE_MODELS, 'Modello Specifico', readonly=True)
    
    # Generated Odoo domain as a string (e.g., "[('state', '=', 'draft')]")
    # For simple queries: produced by GPT-4 domain parsing
    # For structured queries: represents the final filtered IDs as a domain comment
    # Stored for debugging, auditing, and query reproducibility
    model_domain = fields.Text('Generated Domain')
    
    # Count of results returned by the search query execution
    # Updated after search is executed
    results_count = fields.Integer('Results Count')
    
    # Raw response text from OpenAI API (stored for debugging)
    # Contains either a Odoo domain list or JSON structured query spec
    # Helpful for troubleshooting when the LLM doesn't generate valid queries
    raw_response = fields.Text('Raw LLM Response')
    
    # One2many relationship to SearchResult records
    # Contains all the records found by the search domain or structured query
    # Records are linked via query_id in the search.result model
    result_ids = fields.One2many('search.result', 'query_id', 'Results')
    
    # Status of the query: 'draft' = initial, 'success' = completed, 'error' = failed
    # Updated after action_execute_search() is called
    status = fields.Selection([
        ('draft', 'Draft'),
        ('success', 'Success'),
        ('error', 'Error'),
    ], default='draft')
    
    # Error message in case of failures (API key missing, invalid domain, etc.)
    # Populated only when status = 'error'
    error_message = fields.Text('Error Message')
    
    # Reference to the user who created this query
    # Set automatically when query is created
    created_by_user = fields.Many2one('res.users', 'Created By', default=lambda self: self.env.user)
    
    # Flag indicating if this is a structured/complex query (count_aggregate, exclusion)
    # Set to True when LLM recognizes a multi-model or aggregation query
    # Used for filtering and user awareness of query complexity
    is_multi_model = fields.Boolean('Is Structured Query', default=False, readonly=True)
    
    # Query type classification: determines execution method
    # - simple_domain: Standard Odoo domain filter, executes via Model.search()
    # - count_aggregate: Count-based filter across related records
    # - exclusion: Inverse filter (records NOT present in related model)
    # Set by _parse_query_response() based on LLM response parsing
    query_type = fields.Selection([
        ('simple_domain', 'Simple Domain Filter'),
        ('count_aggregate', 'Count Aggregation'),
        ('exclusion', 'Exclusion Filter'),
    ], 'Query Type', readonly=True, default='simple_domain')
    
    # Structured query specification in JSON format
    # Only populated for complex queries (count_aggregate, exclusion)
    # Contains metadata like:
    #   - primary_model: The model whose records are returned
    #   - secondary_model: The model used for filtering/counting
    #   - link_field: Field that links primary to secondary
    #   - threshold: (count_aggregate) minimum/maximum count
    #   - comparison: (count_aggregate) '>=', '>', '<=', '<', '='
    query_spec = fields.Text('Query Specification (JSON)', readonly=True)
    
    # Flag indicating if SQL fallback was used instead of Odoo domain
    # Future feature: reserved for potential SQL generation when domain is insufficient
    # Currently always False (not used in v2.0, reserved for future extensions)
    used_sql_fallback = fields.Boolean('Used SQL Fallback', default=False, readonly=True)

    def action_execute_search(self):
        """
        Main execution method for natural language search.
        
        Flow:
        1. Delete any previous results for this query
        2. Validate category/model selection
        3. Parse natural language to Odoo domain or structured query using LLM
        4. Detect query type: simple domain vs. structured (count_aggregate, exclusion)
        5. Set is_multi_model flag appropriately
        6. Execute the search
        7. Store results in search.result records
        8. Update status (success/error) and error messages
        """
        for record in self:
            try:
                record.result_ids.unlink()
                record._execute_single_model_search()
                    
            except Exception as e:
                record.status = 'error'
                record.error_message = str(e)
                _logger.error(f"Error executing search: {e}")
    
    def _execute_single_model_search(self):
        """
        Execute a standard single-model search with automatic SQL fallback.
        
        Flow:
        1. Validate category and select model
        2. Try generating Odoo domain from natural language
        3. If domain is empty or invalid, detect if SQL is needed
        4. If SQL is needed, generate and execute SQL query
        5. Store results and execution metadata
        """
        if not self.category:
            raise UserError(_('Please select a category (Clienti, Prodotti, etc.) before searching.'))
        
        available_models = self.CATEGORY_MODELS.get(self.category, ['res.partner'])
        
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
            category_label = dict(self._fields['category'].selection).get(self.category, self.category)
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
        
        self.model_name = valid_model
        _logger.warning(f"[SELECT] Category {self.category} → Model {valid_model}")
        
        # Parse natural language to get either domain (list) or structured query (dict)
        query_response = self._parse_natural_language()
        
        # Check if response is structured query (dict with query_type) or simple domain (list)
        if isinstance(query_response, dict) and 'query_type' in query_response:
            _logger.warning(f"[STRUCTURED] Recognized query type: {query_response['query_type']}")
            self.query_type = query_response['query_type']
            self.query_spec = json.dumps(query_response)
            self.is_multi_model = True
            self._execute_structured_query(query_response)
        else:
            # Simple domain query
            self.query_type = 'simple_domain'
            self.is_multi_model = False
            domain = query_response if isinstance(query_response, list) else []
            self.model_domain = str(domain)
            
            # Execute domain search
            Model = self.env[self.model_name]
            results = Model.search(domain)
            self.results_count = len(results)
            self.status = 'success'
            
            result_data = []
            for res in results:
                result_data.append((0, 0, {
                    'record_id': res.id,
                    'record_name': res.display_name,
                    'model': self.model_name,
                }))
            self.result_ids = result_data
    
    def _execute_structured_query(self, query_spec):
        """
        Execute a query from structured specification (JSON).
        
        This method handles queries that the LLM identifies as needing aggregation,
        counting, or exclusion logic. Instead of trying to express this in Odoo domain
        syntax (which is impossible), the LLM responds with JSON metadata.
        
        Args:
            query_spec (dict): Structured query specification with keys:
                - query_type: 'count_aggregate' or 'exclusion'
                - primary_model: Model to return results from
                - secondary_model: Model to aggregate/filter from
                - link_field: Field linking primary to secondary
                - threshold: (for count_aggregate) minimum count
                - comparison: (for count_aggregate) '>=' or other operator
        
        Examples:
            {
              'query_type': 'count_aggregate',
              'primary_model': 'res.partner',
              'secondary_model': 'account.move',
              'link_field': 'partner_id',
              'threshold': 10,
              'comparison': '>='
            }
        """
        try:
            query_type = query_spec.get('query_type')
            _logger.warning(f"[STRUCTURED-EXEC] Executing query type: {query_type}")
            
            if query_type == 'count_aggregate':
                self._execute_count_aggregate_from_spec(query_spec)
            elif query_type == 'exclusion':
                self._execute_exclusion_from_spec(query_spec)
            else:
                raise UserError(_(f'Unknown query type: {query_type}'))
            
            self.status = 'success'
            _logger.warning(f"[STRUCTURED-EXEC] Success: {self.results_count} results")
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"[STRUCTURED-EXEC ERROR] {str(e)}")
            self.status = 'error'
            self.error_message = str(e)
            raise UserError(_(
                'Structured query execution failed: %s\n\n'
                'The AI may have generated invalid query parameters.\n'
                'Try rephrasing your query.'
            ) % str(e)[:100])
    
    def _execute_count_aggregate_from_spec(self, query_spec):
        """
        Execute count aggregation from structured spec.
        
        Finds records in primary_model that have >= N related records in secondary_model.
        
        Example:
            query_spec = {
              'primary_model': 'res.partner',
              'secondary_model': 'account.move',
              'link_field': 'partner_id',
              'threshold': 10,
              'comparison': '>='
            }
        """
        primary_model_name = query_spec['primary_model']
        secondary_model_name = query_spec['secondary_model']
        link_field = query_spec['link_field']
        threshold = query_spec.get('threshold', 1)
        comparison = query_spec.get('comparison', '>=')
        
        _logger.warning(f"[STRUCTURED-AGG] Aggregating {secondary_model_name} by {link_field}")
        _logger.warning(f"[STRUCTURED-AGG] Threshold: {comparison} {threshold}")
        
        PrimaryModel = self.env[primary_model_name]
        SecondaryModel = self.env[secondary_model_name]
        
        # Count records per primary ID
        secondary_records = SecondaryModel.search([])
        counts = {}
        
        for record in secondary_records:
            try:
                link_value = record[link_field]
                if link_value:
                    link_id = link_value.id if hasattr(link_value, 'id') else link_value
                    counts[link_id] = counts.get(link_id, 0) + 1
            except:
                pass
        
        # Filter by comparison operator
        matching_ids = []
        for primary_id, count in counts.items():
            if comparison == '>=':
                if count >= threshold:
                    matching_ids.append(primary_id)
            elif comparison == '>':
                if count > threshold:
                    matching_ids.append(primary_id)
            elif comparison == '<=':
                if count <= threshold:
                    matching_ids.append(primary_id)
            elif comparison == '<':
                if count < threshold:
                    matching_ids.append(primary_id)
            elif comparison == '=':
                if count == threshold:
                    matching_ids.append(primary_id)
        
        _logger.warning(f"[STRUCTURED-AGG] Found {len(matching_ids)} {primary_model_name} records")
        
        # Search primary model with matched IDs
        if matching_ids:
            results = PrimaryModel.search([('id', 'in', matching_ids)])
        else:
            results = PrimaryModel.search([('id', '=', False)])  # Empty result
        
        self.results_count = len(results)
        self.model_domain = f"[('id', 'in', {matching_ids})]  # Structured: count aggregation"
        
        result_data = []
        for res in results:
            result_data.append((0, 0, {
                'record_id': res.id,
                'record_name': res.display_name,
                'model': primary_model_name,
            }))
        self.result_ids = result_data
    
    def _execute_exclusion_from_spec(self, query_spec):
        """
        Execute exclusion query from structured spec.
        
        Finds records in primary_model that have NO related records in secondary_model.
        
        Example: "Products never ordered"
            query_spec = {
              'primary_model': 'product.template',
              'secondary_model': 'sale.order',
              'link_field': 'product_id'
            }
        """
        primary_model_name = query_spec['primary_model']
        secondary_model_name = query_spec['secondary_model']
        link_field = query_spec['link_field']
        
        _logger.warning(f"[STRUCTURED-EXC] Finding {primary_model_name} NOT in {secondary_model_name}")
        
        PrimaryModel = self.env[primary_model_name]
        SecondaryModel = self.env[secondary_model_name]
        
        # Find all primary IDs referenced in secondary model
        secondary_records = SecondaryModel.search([])
        referenced_ids = set()
        
        for record in secondary_records:
            try:
                link_value = record[link_field]
                if link_value:
                    link_id = link_value.id if hasattr(link_value, 'id') else link_value
                    referenced_ids.add(link_id)
            except:
                pass
        
        _logger.warning(f"[STRUCTURED-EXC] Found {len(referenced_ids)} referenced IDs")
        
        # Search primary model NOT in referenced IDs
        if referenced_ids:
            results = PrimaryModel.search([('id', 'not in', list(referenced_ids))])
        else:
            # If nothing is referenced, return all active records
            results = PrimaryModel.search([('active', '=', True)])
        
        self.results_count = len(results)
        self.model_domain = f"[('id', 'not in', {list(referenced_ids)})]  # Structured: exclusion"
        
        result_data = []
        for res in results:
            result_data.append((0, 0, {
                'record_id': res.id,
                'record_name': res.display_name,
                'model': primary_model_name,
            }))
        self.result_ids = result_data

    def _parse_natural_language(self):
        """
        Convert natural language query to either Odoo domain or structured query format.
        
        Returns either:
        - Simple domain: [('field', 'operator', 'value')]  (list)
        - Structured query: {'query_type': 'count_aggregate', ...}  (dict)
        
        Process:
        1. Retrieve OpenAI API key
        2. Build prompt with field info AND examples of structured queries
        3. Send to GPT-4
        4. Try to parse response as JSON first (structured query)
        5. If JSON fails, parse as domain list (simple query)
        6. Return either dict or list depending on what was recognized
        
        The LLM intelligently decides:
        - Simple filter? → Return domain list
        - Needs COUNT/JOIN? → Return JSON with query_type and metadata
        
        Returns:
            dict or list: Structured query dict OR Odoo domain list
            
        Raises:
            UserError: If API key missing, parsing fails, etc.
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
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an intelligent Odoo query generator. "
                            "For SIMPLE queries, respond with Python domain syntax: [('field', 'op', 'value')] "
                            "For COMPLEX queries (aggregation, counting, exclusion), respond with JSON metadata: "
                            '{"query_type": "count_aggregate", "primary_model": "...", ...} '
                            "Respond ONLY with the domain list or JSON. No explanations, no markdown."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            response_text = response.choices[0].message.content.strip()
            self.raw_response = response_text
            _logger.warning(f"[LLM] Response received: {response_text[:300]}")
            
            # Try to parse as JSON first (structured query)
            query_response = self._parse_query_response(response_text)
            return query_response
            
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
    
    def _parse_query_response(self, response_text):
        """
        Parse LLM response as either JSON (structured query) or domain (simple query).
        
        Intelligently detects which format the LLM returned:
        1. Try JSON parsing first (structured query with query_type)
        2. If JSON fails, try domain parsing (list of tuples)
        3. Return either dict or list
        
        Args:
            response_text (str): Raw response from LLM
            
        Returns:
            dict: Structured query if JSON is valid and has query_type
            list: Odoo domain if response is a valid Python list
            
        Log prefixes:
        - [PARSE-JSON] - JSON parsing phase
        - [PARSE-DOMAIN] - Domain parsing phase (fallback)
        """
        response_text = response_text.strip()
        
        # First attempt: try JSON parsing
        _logger.warning(f"[PARSE-JSON] Attempting JSON parse: {response_text[:200]}")
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and 'query_type' in data:
                _logger.warning(f"[PARSE-JSON] ✓ Parsed as structured query: type={data.get('query_type')}")
                return data
            else:
                _logger.warning(f"[PARSE-JSON] JSON is valid but not structured query (no query_type)")
        except json.JSONDecodeError as e:
            _logger.warning(f"[PARSE-JSON] JSON parsing failed: {str(e)[:100]}")
        
        # Second attempt: try domain parsing
        _logger.warning(f"[PARSE-DOMAIN] Parsing as Odoo domain")
        domain = self._parse_domain_response(response_text)
        _logger.warning(f"[PARSE-DOMAIN] Parsed domain: {domain}")
        return domain

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
        
        prompt = f"""TASK: Convert natural language query to Odoo query (domain or structured format).

===== DECISION TREE =====
1. Is this a SIMPLE filter? (e.g., "active invoices", "clients from Milan")
   → Respond with Python domain list: [('field', 'operator', 'value')]

2. Is this a COMPLEX query? (requires counting, aggregation, or exclusion)
   Examples: "Clients with 10+ invoices", "Products never ordered"
   → Respond with JSON metadata:
   {{"query_type": "count_aggregate", "primary_model": "res.partner", ...}}

===== MODEL INFORMATION =====
Model: {self.model_name}
Description: {self._get_model_description()}

===== AVAILABLE FIELDS (DATABASE STORED ONLY) =====
{fields_info}

===== FIELD EXAMPLES FOR THIS MODEL =====
{model_examples}

===== SIMPLE DOMAIN RULES =====
1. Respond with ONLY: [(...), (...)]
2. Field names must EXACTLY match the list above
3. Operators: '=', '!=', '>', '<', '>=', '<=', 'ilike', 'like', 'in', 'not in'
4. Dates: YYYY-MM-DD format
5. Numbers: plain integers/floats (100, not 100€)
6. Booleans: True/False (no quotes)

===== STRUCTURED QUERY RULES (Complex queries) =====
Respond with JSON when query needs multi-model logic:

PATTERN 1 - COUNT AGGREGATION: "Clients with 10+ invoices"
{{
  "query_type": "count_aggregate",
  "primary_model": "res.partner",
  "secondary_model": "account.move",
  "link_field": "partner_id",
  "threshold": 10,
  "comparison": ">="
}}

PATTERN 2 - EXCLUSION: "Products never ordered"
{{
  "query_type": "exclusion",
  "primary_model": "product.template",
  "secondary_model": "sale.order",
  "link_field": "product_id"
}}

===== RESPONSE EXAMPLES =====

SIMPLE DOMAIN QUERIES:
[('state', '=', 'confirmed')]
[('name', 'ilike', 'test'), ('active', '=', True)]
[('amount_total', '>', 1000)]
[]

STRUCTURED QUERIES:
{{"query_type": "count_aggregate", "primary_model": "res.partner", "secondary_model": "account.move", "link_field": "partner_id", "threshold": 3, "comparison": ">="}}
{{"query_type": "exclusion", "primary_model": "product.template", "secondary_model": "sale.order", "link_field": "product_id"}}

===== YOUR TASK =====
Query: "{self.name}"

Analyze: Does this query need multi-model logic (counting, aggregation)?
- YES → Respond ONLY with JSON (structured query)
- NO → Respond ONLY with domain list [(...)]

Response:"""
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
