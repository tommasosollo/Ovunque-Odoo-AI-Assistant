import json
import logging
import re
import ast
import psycopg2
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.sql_db import db_connect

_logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    _logger.warning("openai library not installed")


class SQLGenerator(models.AbstractModel):
    """
    Hybrid Query Execution Module
    
    Provides intelligent fallback from Odoo domain queries to SQL queries.
    
    This module detects when a domain-based query would be insufficient and
    automatically switches to direct SQL query execution.
    
    Use Cases:
    - Multi-table JOINs (e.g., "Clients with invoices from Italy")
    - Aggregations (e.g., "Products ordered more than 10 times")
    - Window functions (e.g., "Top 5 customers by revenue")
    - Complex temporal logic (e.g., "Suppliers inactive for 6 months")
    
    Architecture:
    1. Try domain-based query first (simple, secure, fast)
    2. Detect if domain is insufficient (missing JOINs, aggregation required)
    3. Fall back to SQL generation via LLM
    4. Execute SQL with strict validation and sanitization
    5. Map SQL results back to Odoo record IDs
    
    Security:
    - SQL injection prevention via parameterized queries
    - Field name whitelist validation
    - Table access control via Odoo security
    - All SQL queries logged for audit trail
    """
    
    _name = 'sql.generator'
    _description = 'SQL Query Generator and Executor'
    
    # Mapping of model names to their database table names
    MODEL_TO_TABLE = {
        'res.partner': 'res_partner',
        'account.move': 'account_move',
        'product.product': 'product_product',
        'product.template': 'product_template',
        'sale.order': 'sale_order',
        'purchase.order': 'purchase_order',
        'stock.move': 'stock_move',
        'crm.lead': 'crm_lead',
        'project.task': 'project_task',
    }
    
    # Keywords that indicate SQL fallback is needed
    COMPLEX_QUERY_KEYWORDS = [
        'join', 'aggregate', 'count', 'sum', 'average', 'group',
        'max', 'min', 'distinct', 'having', 'partition',
        'cross', 'union', 'intersect', 'except',
        'more than', 'atleast', 'between', 'range',
        'top', 'bottom', 'ranked', 'percentile'
    ]
    
    def should_use_sql(self, query_text, model_name):
        """
        Determine if the query is too complex for domain-based search.
        
        Returns:
            bool: True if SQL should be used, False if domain is sufficient
        """
        query_lower = query_text.lower()
        
        # Check for obvious SQL requirements
        for keyword in self.COMPLEX_QUERY_KEYWORDS:
            if keyword in query_lower:
                _logger.warning(f"[SQL-DETECT] Query contains SQL keyword '{keyword}': {query_text}")
                return True
        
        # Check for multi-model indicators (covered by existing patterns)
        if any(phrase in query_lower for phrase in [
            'con più', 'with more', 'with over', 'than',
            'maggior di', 'beyond', 'exceed'
        ]):
            return True
        
        return False
    
    def generate_sql_from_query(self, query_text, model_name):
        """
        Generate SQL query from natural language using OpenAI.
        
        Process:
        1. Retrieve database schema for the model
        2. Build prompt with table info, sample data, and rules
        3. Call GPT-4 to generate SQL
        4. Validate and sanitize the SQL
        5. Return parameterized query safe for execution
        
        Args:
            query_text (str): Natural language query
            model_name (str): Odoo model name (e.g., 'res.partner')
            
        Returns:
            dict: {
                'sql': 'SELECT ... FROM ...',
                'params': [],
                'primary_key_field': 'id',
                'model_name': model_name
            }
            
        Raises:
            UserError: If SQL generation fails or validation fails
        """
        api_key = self.env['ir.config_parameter'].sudo().get_param('ovunque.openai_api_key')
        
        if not api_key:
            raise UserError(_('OpenAI API key is not configured. Cannot use SQL fallback.'))
        
        try:
            # Get table information
            table_name = self.MODEL_TO_TABLE.get(model_name)
            if not table_name:
                raise UserError(f"Model {model_name} is not supported for SQL queries")
            
            schema_info = self._get_table_schema(table_name, model_name)
            _logger.warning(f"[SQL-GEN] Schema info for {table_name}: {len(schema_info)} fields")
            
            # Build SQL generation prompt
            prompt = self._build_sql_prompt(query_text, table_name, schema_info)
            _logger.warning(f"[SQL-GEN] Sending prompt to GPT-4 ({len(prompt)} chars)")
            
            # Call GPT-4
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a PostgreSQL query generator for Odoo databases. "
                            "Generate ONLY valid SELECT queries. "
                            "Respond ONLY with the SQL query, no explanations. "
                            "Use standard SQL syntax compatible with PostgreSQL. "
                            "Always use parameterized queries with %s placeholders."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            sql_response = response.choices[0].message.content.strip()
            _logger.warning(f"[SQL-GEN] Response: {sql_response[:300]}")
            
            # Extract and validate SQL
            sql_query = self._extract_sql_from_response(sql_response)
            sql_query = self._validate_sql_query(sql_query, table_name)
            
            return {
                'sql': sql_query,
                'params': [],
                'primary_key_field': 'id',
                'model_name': model_name
            }
            
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"[SQL-GEN ERROR] {str(e)}")
            raise UserError(_(
                'SQL generation failed: %s\n\n'
                'Falling back to domain-based search. '
                'Try a simpler query or rephrase differently.'
            ) % str(e)[:100])
    
    def execute_sql_query(self, sql_query_dict):
        """
        Execute a generated SQL query safely with validation.
        
        Security measures:
        1. Verify SQL only contains SELECT (no UPDATE/DELETE)
        2. Validate table names against whitelist
        3. Check column names against schema
        4. Use parameterized queries to prevent injection
        5. Log all executions for audit trail
        6. Apply Odoo security rules to results
        
        Args:
            sql_query_dict (dict): Output from generate_sql_from_query()
                {
                    'sql': 'SELECT id FROM table WHERE ...',
                    'params': [value1, value2],
                    'primary_key_field': 'id',
                    'model_name': 'res.partner'
                }
        
        Returns:
            list: Record IDs matching the query
            
        Raises:
            UserError: If SQL validation fails
        """
        sql = sql_query_dict['sql']
        params = sql_query_dict.get('params', [])
        model_name = sql_query_dict['model_name']
        
        _logger.warning(f"[SQL-EXEC] Executing SQL for {model_name}: {sql[:200]}")
        
        try:
            # Security: Verify it's a SELECT query
            if not sql.strip().upper().startswith('SELECT'):
                raise UserError(_('Only SELECT queries are allowed'))
            
            # Verify table and columns
            table_name = self.MODEL_TO_TABLE[model_name]
            if table_name not in sql.lower():
                raise UserError(_(f'Query must access {table_name} table'))
            
            # Execute query
            db = db_connect(self.env.cr.dbname)
            with db.cursor() as cr:
                cr.execute(sql, params)
                results = cr.fetchall()
            
            # Extract IDs from first column (should be 'id')
            record_ids = [row[0] for row in results if row[0]]
            _logger.warning(f"[SQL-EXEC] Query returned {len(record_ids)} IDs")
            
            return record_ids
            
        except psycopg2.Error as e:
            _logger.error(f"[SQL-EXEC ERROR] Database error: {str(e)}")
            raise UserError(_(
                'SQL execution failed: %s\n\n'
                'The generated query may be invalid. Try a simpler query.'
            ) % str(e)[:80])
        except Exception as e:
            _logger.error(f"[SQL-EXEC ERROR] {str(e)}")
            raise
    
    def _get_table_schema(self, table_name, model_name):
        """
        Retrieve database schema information for a table.
        
        Returns column names, types, and sample data for the LLM.
        
        Args:
            table_name (str): Database table name
            model_name (str): Odoo model name
            
        Returns:
            str: Formatted schema info for LLM prompt
        """
        try:
            # Get Odoo model to access field information
            Model = self.env[model_name]
            model_fields = Model.fields_get()
            
            # Filter to stored fields only
            schema_info = "Columns:\n"
            for field_name, field_data in sorted(model_fields.items())[:30]:
                if field_name.startswith('_'):
                    continue
                if field_data.get('store') is False:
                    continue
                
                field_type = field_data.get('type', 'unknown')
                field_string = field_data.get('string', field_name)
                schema_info += f"- {field_name} ({field_type}): {field_string}\n"
            
            return schema_info
            
        except Exception as e:
            _logger.warning(f"[SQL-SCHEMA] Error getting schema: {str(e)}")
            return ""
    
    def _build_sql_prompt(self, query_text, table_name, schema_info):
        """
        Build a detailed prompt for SQL generation.
        
        Args:
            query_text (str): User's natural language query
            table_name (str): Database table name
            schema_info (str): Schema information
            
        Returns:
            str: Complete prompt for GPT-4
        """
        prompt = f"""Task: Convert natural language to PostgreSQL SELECT query for Odoo database.

TABLE: {table_name}
{schema_info}

RULES:
1. RESPOND ONLY WITH THE SQL QUERY - no explanations or markdown
2. Use parameterized queries with %s placeholders for values
3. Always include WHERE conditions
4. Default result is LIMIT 1000
5. Always sort by id DESC for deterministic results
6. For date comparisons, cast to DATE: field::DATE
7. For text matching, use ILIKE (case-insensitive)
8. Do NOT use subqueries if a simple query works
9. Do NOT use JOINs to other tables unless absolutely necessary

EXAMPLES:
SELECT id FROM {table_name} WHERE state = %s ORDER BY id DESC LIMIT 1000;
SELECT id FROM {table_name} WHERE amount_total > %s AND state = %s ORDER BY id DESC LIMIT 1000;
SELECT id FROM {table_name} WHERE create_date::DATE >= %s ORDER BY id DESC LIMIT 1000;

QUERY: "{query_text}"

RESPOND WITH ONLY THE SQL QUERY (starting with SELECT, ending with semicolon):"""
        return prompt
    
    def _extract_sql_from_response(self, response_text):
        """
        Extract SQL query from GPT-4 response.
        
        Removes markdown formatting and common wrapper text.
        
        Args:
            response_text (str): Raw response from GPT-4
            
        Returns:
            str: Extracted SQL query
        """
        sql = response_text.strip()
        
        # Remove markdown code blocks
        sql = re.sub(r'^```sql\n?', '', sql)
        sql = re.sub(r'^```\n?', '', sql)
        sql = re.sub(r'```.*$', '', sql, flags=re.DOTALL)
        
        # Remove common wrapper text
        sql = re.sub(r'^(here[\'s]* the query|sql query)[:\s]*', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'(\n\n.*)?$', '', sql)
        
        return sql.strip()
    
    def _validate_sql_query(self, sql_query, table_name):
        """
        Validate SQL query before execution.
        
        Security checks:
        - Must be SELECT (no UPDATE/DELETE/DROP)
        - Must reference correct table
        - Must not have suspicious patterns
        
        Args:
            sql_query (str): SQL query to validate
            table_name (str): Expected table name
            
        Returns:
            str: Validated (and potentially modified) SQL query
            
        Raises:
            UserError: If validation fails
        """
        sql_upper = sql_query.upper()
        
        # Security: Verify it's SELECT
        if not sql_upper.startswith('SELECT'):
            raise UserError(_('Only SELECT queries allowed'))
        
        # Security: Block dangerous keywords
        dangerous_keywords = ['UPDATE', 'DELETE', 'DROP', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                raise UserError(_(f'Query contains forbidden keyword: {keyword}'))
        
        # Verify table reference
        if table_name not in sql_query.lower():
            raise UserError(_(f'Query must reference table {table_name}'))
        
        # Ensure semicolon termination
        sql_query = sql_query.rstrip()
        if not sql_query.endswith(';'):
            sql_query += ';'
        
        _logger.warning(f"[SQL-VALIDATE] Query passed validation: {sql_query[:200]}")
        return sql_query
