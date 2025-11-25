import requests
import json
from odoo import models

class AIService(models.AbstractModel):
    _name = "ai.data.assistant.service"
    _description = "LLM Service for Data Assistant"

    def _call_llm(self, prompt):
        icp = self.env["ir.config_parameter"].sudo()
        api_key = icp.get_param("ai_data_assistant.api_key")
        if not api_key:
            raise ValueError("API key non configurata")

        url = "https://api.openai.com/v1/responses"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "gpt-4.1-mini",
            "input": prompt
        }

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()

            output = data.get("output", [])
            if not output:
                raise ValueError("LLM ha restituito output vuoto")

            # estrai solo il testo
            for item in output:
                if isinstance(item, dict) and "content" in item:
                    for c in item["content"]:
                        if c.get("type") == "text":
                            return c["text"]

            raise ValueError("Formato risposta LLM non valido")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"Errore nella chiamata all'LLM: {str(e)}") from e