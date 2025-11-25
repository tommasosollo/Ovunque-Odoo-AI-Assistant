import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class SearchController(http.Controller):
    
    @http.route('/ovunque/search', type='jsonrpc', auth='user', methods=['POST'])
    def natural_language_search(self, **kwargs):
        """API endpoint for natural language search"""
        try:
            query_text = kwargs.get('query')
            model_name = kwargs.get('model')
            
            if not query_text or not model_name:
                return {
                    'success': False,
                    'error': 'Missing query or model parameter'
                }
            
            SearchQuery = request.env['search.query']
            search_record = SearchQuery.create({
                'name': query_text,
                'model_name': model_name,
            })
            
            search_record.action_execute_search()
            
            if search_record.status == 'success':
                Model = request.env[model_name]
                domain = eval(search_record.model_domain)
                results = Model.search(domain)
                
                results_data = []
                for record in results[:50]:
                    results_data.append({
                        'id': record.id,
                        'display_name': record.display_name,
                    })
                
                return {
                    'success': True,
                    'results': results_data,
                    'count': len(results),
                    'domain': search_record.model_domain,
                    'query_id': search_record.id,
                }
            else:
                return {
                    'success': False,
                    'error': search_record.error_message
                }
                
        except Exception as e:
            _logger.error(f"Search API error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/ovunque/models', type='jsonrpc', auth='user')
    def get_available_models(self, **kwargs):
        """Get list of available models for search"""
        try:
            SearchQuery = request.env['search.query']
            available_models = []
            
            for model_code, model_label in SearchQuery.AVAILABLE_MODELS:
                available_models.append({
                    'name': model_code,
                    'label': model_label,
                })
            
            return {
                'success': True,
                'models': available_models
            }
        except Exception as e:
            _logger.error(f"Get models error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
