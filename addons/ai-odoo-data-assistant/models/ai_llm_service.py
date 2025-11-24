import requests
from odoo import fields, models

class AIService(models.AbstractModel):
    _name = "ai.data.assistant.service"
    _description = "LLM Service for Data Assistant"

    def _call_llm(self, prompt):
        icp = self.env["ir.config_parameter"].sudo()
        api_key = icp.get_param("ai_data_assistant.api_key")
        model = icp.get_param("ai_data_assistant.model_name", "gpt-4o-mini")

        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}

        url = "https://api.openai.com/v1/chat/completions"

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]
