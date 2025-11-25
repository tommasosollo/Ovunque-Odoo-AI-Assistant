from odoo import models, fields

class DuplicateCheckerWizard(models.TransientModel):
    _name = "ai.duplicate.checker.wizard"
    _description = "Popup for duplicate suggestions"

    suggestions = fields.Text("Suggestions", readonly=True)
    duplicates = fields.Text("Possible Duplicates", readonly=True)
    normalized_values = fields.Text("Normalized Values", readonly=True)

    def action_apply(self):
        # TODO: implementare merge/replace
        return True