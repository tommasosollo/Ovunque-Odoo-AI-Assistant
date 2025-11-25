"""
Utility functions for Ovunque module
"""

import logging
from odoo import api, fields

_logger = logging.getLogger(__name__)


def setup_api_key(env, api_key):
    """
    Setup OpenAI API key in Odoo config
    
    Args:
        env: Odoo environment
        api_key: OpenAI API key
    
    Example:
        from ovunque.utils import setup_api_key
        setup_api_key(self.env, 'sk-...')
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
    Get model fields in a format suitable for LLM prompts
    
    Args:
        env: Odoo environment
        model_name: Name of the model
        limit: Maximum number of fields to return
    
    Returns:
        Formatted string with field information
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
    Parse search results into a readable format
    
    Args:
        records: Recordset of search results
        max_results: Maximum results to return
    
    Returns:
        List of dicts with id and display_name
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
    Validate that domain is a proper Odoo domain
    
    Args:
        domain: Domain to validate (should be a list of tuples)
    
    Returns:
        True if valid, False otherwise
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
    Return common search pattern examples
    
    Returns:
        Dict with model names and example queries
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
