from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    ai_models_to_check_ids = fields.One2many(
        'ai.assistant.model.selection',
        'company_id',
        string='Models to check',
    )