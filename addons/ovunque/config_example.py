"""
Configuration example for Ovunque module

After installing the module, run this script to set the OpenAI API key:
python odoo-bin -d database_name -c config.conf --script config_example.py
"""

import os
from dotenv import load_dotenv
from odoo import api, SUPERUSER_ID
from odoo.cli import main

def configure_ovunque(cr, uid, context=None):
    """Configure Ovunque with OpenAI API key"""
    
    load_dotenv()
    
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set!")
        print("Please set it in your .env file or system environment")
        return
    
    env = api.Environment(cr, SUPERUSER_ID, context or {})
    
    env['ir.config_parameter'].sudo().set_param('ovunque.openai_api_key', api_key)
    
    print(f"✓ OpenAI API key configured successfully!")
    print(f"  Key: {api_key[:10]}...{api_key[-4:]}")


if __name__ == '__main__':
    configure_ovunque(None, None)
