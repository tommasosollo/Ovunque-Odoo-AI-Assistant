from odoo import models

class DataCleaner(models.AbstractModel):
    _name = "ai.data.cleaner"
    _inherit = "ai.data.assistant.service"
    _description = "LLM-based Data Cleaner"

    def analyze_record(self, model_name, values):
        prompt = f"""
Sei un assistente per la pulizia dei dati Odoo.
MODEL: {model_name}
VALUES: {values}

Compiti:
1. Identifica possibili duplicati basandoti su nome, email, codice, descrizione.
2. Suggerisci normalizzazioni.
3. Restituisci SOLO un JSON valido con:
{{"duplicates": [...], "normalized_values": {{...}}}}
"""
        return self._call_llm(prompt)