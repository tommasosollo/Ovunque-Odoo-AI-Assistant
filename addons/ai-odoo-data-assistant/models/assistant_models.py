from odoo import models, api
import json

class AIAssistantMixin(models.AbstractModel):
    _name = "ai.assistant.mixin"
    _description = "Mixin for AI assisted record creation"

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        for record, values in zip(result, vals_list):
            self._trigger_ai_cleaner(record, values)
        return result

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            self._trigger_ai_cleaner(record, vals)
        return res

    def _trigger_ai_cleaner(self, record, values):
        cleaner = self.env["ai.data.cleaner"]
        response = cleaner.analyze_record(self._name, values)
        try:
            data = json.loads(response)
        except:
            return

        record.ai_duplicate_data = response

    ai_duplicate_data = fields.Text("AI Duplicate Data", readonly=True)
