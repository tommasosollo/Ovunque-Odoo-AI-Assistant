from odoo import http
from odoo.http import request

class AIAssistantAPI(http.Controller):

    @http.route("/ai_assistant/preview", type="json", auth="user")
    def preview(self, model, values):
        cleaner = request.env["ai.data.cleaner"].sudo()
        return cleaner.analyze_record(model, values)
