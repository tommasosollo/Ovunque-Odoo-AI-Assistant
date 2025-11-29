{
    'name': 'Ovunque - Natural Language Search for Odoo',
    'version': '19.0.2.0.0',
    'category': 'Tools',
    'summary': 'Search your Odoo data using natural language with AI - Now with multi-model queries!',
    'author': 'Your Company',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/search_query_views.xml',
        'views/menu.xml',
    ],
    'external_dependencies': {
        'python': [
            'openai',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
