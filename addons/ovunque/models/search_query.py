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
    _name = 'search.query'
    _description = 'Natural Language Search Query'
    _order = 'create_date desc'

    AVAILABLE_MODELS = [
        ('res.partner', 'Partner / Contact'),
        ('account.move', 'Invoice'),
        ('product.product', 'Product'),
        ('sale.order', 'Sales Order'),
        ('purchase.order', 'Purchase Order'),
        ('stock.move', 'Stock Move'),
        ('crm.lead', 'CRM Lead'),
        ('project.task', 'Project Task'),
    ]

    name = fields.Char('Query Text', required=True)
    model_name = fields.Selection(AVAILABLE_MODELS, 'Target Model', required=True, default='res.partner')
    model_domain = fields.Text('Generated Domain')
    results_count = fields.Integer('Results Count')
    raw_response = fields.Text('Raw LLM Response')
    result_ids = fields.One2many('search.result', 'query_id', 'Results')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('success', 'Success'),
        ('error', 'Error'),
    ], default='draft')
    error_message = fields.Text('Error Message')
    created_by_user = fields.Many2one('res.users', 'Created By', default=lambda self: self.env.user)

    def action_execute_search(self):
        """Execute the natural language search"""
        for record in self:
            try:
                record.result_ids.unlink()
                
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
        """Convert natural language to Odoo domain using LLM"""
        api_key = self.env['ir.config_parameter'].sudo().get_param('ovunque.openai_api_key')
        
        if not api_key:
            raise UserError(_('OpenAI API key not configured. Please set it in settings.'))
        
        try:
            client = OpenAI(api_key=api_key)
            Model = self.env[self.model_name]
            model_fields = Model.fields_get()
            
            prompt = self._build_prompt(model_fields)
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an Odoo domain filter generator. Convert natural language queries to Odoo domain syntax (Python list of tuples). Respond ONLY with valid Python list syntax."
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
            
            domain = self._parse_domain_response(response_text)
            return domain
            
        except Exception as e:
            _logger.error(f"LLM parsing error: {e}")
            raise UserError(_('Error communicating with OpenAI: %s') % str(e))

    def _build_prompt(self, model_fields):
        """Build the prompt for LLM with available fields"""
        fields_info = self._get_field_info(model_fields)
        
        prompt = f"""You are an Odoo domain filter generator. Your ONLY task is to convert queries to Odoo domain syntax.

Model: {self.model_name}
Available fields:
{fields_info}

Query: "{self.name}"

IMPORTANT RULES:
1. Respond with ONLY a valid Python list - nothing else
2. No explanations, no markdown, no extra text
3. Use only these operators: '=', '!=', '>', '<', '>=', '<=', 'ilike', 'like', 'in', 'not in'
4. If you cannot create a domain, respond with: []
5. Date format must be YYYY-MM-DD when comparing dates
6. For Many2one fields, use .name for text search

Valid examples:
[('state', '=', 'confirmed')]
[('name', 'ilike', 'test'), ('active', '=', True)]
[]

Your response MUST be valid Python. Start with [ and end with ]"""
        return prompt

    def _get_field_info(self, model_fields):
        """Extract and format field information for LLM"""
        fields_info = []
        for field_name, field_data in model_fields.items():
            if field_name.startswith('_'):
                continue
            field_type = field_data.get('type', 'unknown')
            field_string = field_data.get('string', field_name)
            fields_info.append(f"- {field_name} ({field_type}): {field_string}")
        
        return "\n".join(fields_info[:20])

    def _parse_domain_response(self, response_text):
        """Parse the LLM response and validate it"""
        import re
        import ast
        try:
            cleaned = response_text.strip()
            _logger.info(f"Raw response to parse: {cleaned[:200]}")
            
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```python\n?', '', cleaned)
                cleaned = re.sub(r'```.*$', '', cleaned, flags=re.DOTALL).strip()
                _logger.info(f"After removing markdown: {cleaned[:200]}")
            
            match = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(0)
                _logger.info(f"Extracted list: {cleaned[:200]}")
            
            if not cleaned or cleaned == '[]':
                _logger.info("Empty domain, returning []")
                return []
            
            try:
                domain = ast.literal_eval(cleaned)
            except (ValueError, SyntaxError):
                domain = eval(cleaned)
            
            if not isinstance(domain, list):
                raise ValueError("Response is not a list")
            
            _logger.info(f"Successfully parsed domain: {domain}")
            return domain
        except Exception as e:
            _logger.error(f"Domain parsing error: {e}. Raw response: {response_text[:200]}")
            raise UserError(_('Could not parse LLM response as a valid domain. Please try rephrasing your query.'))


class SearchResult(models.Model):
    _name = 'search.result'
    _description = 'Search Query Result'
    _order = 'id desc'

    query_id = fields.Many2one('search.query', 'Query', ondelete='cascade', required=True)
    record_id = fields.Integer('Record ID', required=True)
    record_name = fields.Char('Record Name', required=True)
    model = fields.Char('Model', required=True)
