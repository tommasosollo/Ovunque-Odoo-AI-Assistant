from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ai_api_key = fields.Char("AI API Key", config_parameter="ai_data_assistant.api_key")
    ai_model_name = fields.Char("LLM Model", default="gpt-4o-mini",
                                config_parameter="ai_data_assistant.model_name")
    ai_redundancy_level = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        string="Data Redundancy Analysis Level",
        default="medium",
        config_parameter="ai_data_assistant.redundancy_level",
    )
