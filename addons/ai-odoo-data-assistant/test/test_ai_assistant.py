from odoo.tests.common import TransactionCase

class TestAIAssistant(TransactionCase):

    def test_llm_cleaner(self):
        cleaner = self.env["ai.data.cleaner"]
        result = cleaner.analyze_record("res.partner", {"name": "Mario Rossi"})
        self.assertTrue(result)
