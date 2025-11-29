"""
Utility functions for Ovunque module

This module provides helper functions for:
- Configuring OpenAI API keys
- Extracting model field information
- Parsing and formatting search results
- Validating Odoo domains
- Common search pattern examples

These functions are used by both the models and controllers.
"""

import logging
from odoo import api, fields

_logger = logging.getLogger(__name__)


def setup_api_key(env, api_key):
    """
    Configure the OpenAI API key in Odoo's ir.config_parameter.
    
    This stores the key in the database so it persists across Odoo restarts.
    Can be called from Python shell or initialization scripts.
    
    Args:
        env: Odoo environment
        api_key: OpenAI API key (format: "sk-...")
    
    Returns:
        bool: True if successful, False if error
    
    Example:
        from ovunque.utils import setup_api_key
        setup_api_key(self.env, 'sk-proj-abcdef123456')
    """
    try:
        env['ir.config_parameter'].sudo().set_param('ovunque.openai_api_key', api_key)
        _logger.info("OpenAI API key configured successfully")
        return True
    except Exception as e:
        _logger.error(f"Failed to configure API key: {e}")
        return False


def get_model_fields_for_llm(env, model_name, limit=30):
    """
    Extract model fields and format them as LLM-readable text.
    
    Used to build prompts for the LLM. Returns only stored fields
    with their types and labels, which the LLM can use.
    
    Args:
        env: Odoo environment
        model_name: Full model name (e.g., "res.partner", "account.move")
        limit: Maximum number of fields to return (default 30)
    
    Returns:
        str: Formatted field list with types and labels, or empty string on error
        
    Example:
        fields_text = get_model_fields_for_llm(env, 'res.partner', limit=50)
        # Returns: "- id (integer): ID\n- name (char): Name\n- active (boolean): Active\n..."
    """
    try:
        Model = env[model_name]
        fields_dict = Model.fields_get()
        
        fields_info = []
        for field_name, field_data in fields_dict.items():
            if field_name.startswith('_'):
                continue
            
            field_type = field_data.get('type', 'unknown')
            field_string = field_data.get('string', field_name)
            required = ' (required)' if field_data.get('required') else ''
            
            fields_info.append(f"- {field_name} ({field_type}){required}: {field_string}")
            
            if len(fields_info) >= limit:
                break
        
        return "\n".join(fields_info)
    
    except Exception as e:
        _logger.error(f"Failed to get model fields: {e}")
        return ""


def parse_search_results(records, max_results=50):
    """
    Convert Odoo recordset into a list of dicts for API responses.
    
    Extracts the ID and display_name from each record.
    Limits results to max_results to prevent huge API responses.
    
    Args:
        records: Odoo recordset (result of Model.search())
        max_results: Maximum number of results to return (default 50)
    
    Returns:
        list: List of dicts like [{"id": 1, "display_name": "Name1"}, ...]
    """
    results = []
    for i, record in enumerate(records):
        if i >= max_results:
            break
        results.append({
            'id': record.id,
            'display_name': record.display_name,
        })
    
    return results


def validate_domain(domain):
    """
    Validate that a domain has correct structure for Odoo.
    
    A valid Odoo domain is a list where each element is a 3-tuple:
    [
        ('field1', 'operator', value1),
        ('field2', 'operator', value2),
    ]
    
    Args:
        domain: Domain to validate (should be a list of tuples)
    
    Returns:
        bool: True if valid structure, False otherwise
        
    Note: This only checks structure, not field existence or operator validity.
    """
    if not isinstance(domain, list):
        return False
    
    for element in domain:
        if not isinstance(element, (tuple, list)):
            return False
        if isinstance(element, (tuple, list)) and len(element) != 3:
            return False
    
    return True


def common_search_patterns():
    """
    Return curated examples of natural language queries for each supported model.
    
    These examples can be used in documentation or as suggestions in the UI
    to help users understand what kinds of queries they can ask.
    
    Returns:
        dict: Keys are model names, values are lists of example queries
        
    Example:
        patterns = common_search_patterns()
        print(patterns['account.move'])
        # Output: ["Unpaid invoices from this month", "All invoices from Rossi in 2024", ...]
    """
    return {
        'account.move': [
            "Unpaid invoices from this month",
            "All invoices from Rossi in 2024",
            "Invoices with amount > 1000",
            "Posted invoices from March",
        ],
        'product.product': [
            "Products in stock below 5 units",
            "All products in Electronics category",
            "Products with price between 10 and 100",
            "Out of stock products",
        ],
        'sale.order': [
            "Shipped orders from last week",
            "Pending orders from Milan customer",
            "Orders with total > 500",
            "Orders from last 30 days",
        ],
        'res.partner': [
            "Suppliers from Tuscany region",
            "Customers who didn't order in 2024",
            "Partners with credit > 10000",
            "All customers from Rome",
        ],
    }
