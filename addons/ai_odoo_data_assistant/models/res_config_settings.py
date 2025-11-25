from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ai_duplicate_checker_enabled = fields.Boolean(
        string="Enable AI Duplicate Checker",
        config_parameter="ai_data_assistant.duplicate_checker_enabled",
    )
    ai_api_key = fields.Char("AI API Key", config_parameter="ai_data_assistant.api_key")
    ai_model_name = fields.Char("LLM Model", default="gpt-4.1-mini",
                                config_parameter="ai_data_assistant.model_name")
    ai_redundancy_level = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        string="Data Redundancy Analysis Level",
        default="medium",
        config_parameter="ai_data_assistant.redundancy_level",
    )

    ai_models_to_check_ids = fields.One2many(
        'ai.assistant.model.selection',
        'company_id',
        string='Models to check',
    )


