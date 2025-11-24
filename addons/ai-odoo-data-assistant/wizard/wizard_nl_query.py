from odoo import models, fields

class NLQueryWizard(models.TransientModel):
    _name = "ai.nl.query.wizard"
    _description = "Natural Language Query Wizard"

    user_query = fields.Text("Ask in Natural Language")

    def action_execute(self):
        engine = self.env["ai.nl.query.engine"]
        q = engine.nl_to_orm(self.user_query)

        records = self.env[q["model"]].search(q["domain"], limit=q.get("limit", 50))
        return {
            "type": "ir.actions.act_window",
            "name": "Query Results",
            "res_model": q["model"],
            "view_mode": "tree,form",
            "domain": q["domain"],
        }
