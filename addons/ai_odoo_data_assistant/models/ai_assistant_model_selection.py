from odoo import fields, models

class AiAssistantModelSelection(models.Model):
    _name = 'ai.assistant.model.selection'
    _description = 'AI Assistant Model Selection'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company.id,
        ondelete='cascade',
    )

    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)
    notes = fields.Char()