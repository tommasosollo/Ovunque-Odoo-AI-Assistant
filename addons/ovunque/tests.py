"""
Unit tests for Ovunque module
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestOvunqueSearchQuery(TransactionCase):
    """Test cases for search.query model"""
    
    def setUp(self):
        super().setUp()
        self.SearchQuery = self.env['search.query']
        
    def test_create_search_query(self):
        """Test creating a search query"""
        query = self.SearchQuery.create({
            'name': 'Test query',
            'model_name': 'res.partner',
        })
        
        self.assertIsNotNone(query.id)
        self.assertEqual(query.name, 'Test query')
        self.assertEqual(query.model_name, 'res.partner')
        self.assertEqual(query.status, 'draft')
    
    def test_search_query_required_fields(self):
        """Test that required fields are enforced"""
        with self.assertRaises(Exception):
            self.SearchQuery.create({
                'name': 'Test query',
            })
    
    def test_search_query_defaults(self):
        """Test default values"""
        query = self.SearchQuery.create({
            'name': 'Test',
            'model_name': 'res.partner',
        })
        
        self.assertEqual(query.status, 'draft')
        self.assertEqual(query.results_count, 0)
        self.assertIsNotNone(query.created_by_user)
    
    def test_domain_parsing(self):
        """Test domain parsing"""
        query = self.SearchQuery.create({
            'name': '[("name", "ilike", "test")]',
            'model_name': 'res.partner',
        })
        
        domain = query._parse_domain_response('[("name", "ilike", "test")]')
        self.assertIsInstance(domain, list)
        self.assertEqual(len(domain), 1)
        self.assertEqual(domain[0][0], 'name')
    
    def test_invalid_model_name(self):
        """Test handling of invalid model names"""
        query = self.SearchQuery.create({
            'name': 'Test query',
            'model_name': 'nonexistent.model',
        })
        
        # This should fail when trying to execute
        with self.assertRaises(Exception):
            query.action_execute_search()


@tagged('post_install', '-at_install')
class TestOvunqueControllers(TransactionCase):
    """Test cases for API controllers"""
    
    def test_models_endpoint(self):
        """Test /ovunque/models endpoint"""
        # This test would require HTTP client setup
        # Implementation depends on test framework
        pass


@tagged('post_install', '-at_install')
class TestOvunqueUtils(TransactionCase):
    """Test cases for utility functions"""
    
    def test_validate_domain(self):
        """Test domain validation"""
        from ovunque import utils
        
        valid_domain = [('name', 'ilike', 'test')]
        self.assertTrue(utils.validate_domain(valid_domain))
        
        invalid_domain = [('name', 'test')]
        self.assertFalse(utils.validate_domain(invalid_domain))
        
        invalid_type = "not a list"
        self.assertFalse(utils.validate_domain(invalid_type))
    
    def test_common_search_patterns(self):
        """Test common search patterns"""
        from ovunque import utils
        
        patterns = utils.common_search_patterns()
        self.assertIn('account.move', patterns)
        self.assertIn('product.product', patterns)
        self.assertGreater(len(patterns['account.move']), 0)
