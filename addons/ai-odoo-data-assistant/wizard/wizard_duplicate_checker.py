from odoo import models, fields

class DuplicateCheckerWizard(models.TransientModel):
    _name = "ai.duplicate.checker.wizard"
    _description = "Popup for duplicate suggestions"

    original_record_id = fields.Many2one("ir.model")
    suggestions = fields.Text("Suggestions", readonly=True)

    def action_apply(self):
        # Applica suggerimenti (implementazione base)
        return True
