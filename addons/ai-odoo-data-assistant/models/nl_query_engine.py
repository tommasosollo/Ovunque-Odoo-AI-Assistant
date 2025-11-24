from odoo import models
import json

class NLQueryEngine(models.AbstractModel):
    _name = "ai.nl.query.engine"
    _inherit = "ai.data.assistant.service"
    _description = "Natural Language Query Engine"

    def nl_to_orm(self, query):
        prompt = f"""
Converti questa richiesta in una istruzione ORM Odoo.
Risposta SOLO in JSON:
{{
 "model": "...",
 "domain": [...],
 "fields": ["..."],
 "limit": 100
}}

Testo: "{query}"
"""
        return json.loads(self._call_llm(prompt))
