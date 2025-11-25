{
    "name": "AI Data Assistant",
    "version": "1.0.0",
    "summary": "LLM-based data dedupe, normalization and natural language querying",
    "author": "Tommaso Sollo",
    "license": "LGPL-3",
    "website": "https://example.com",
    "category": "Productivity/AI",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings.xml",
        "views/ai_assistant_model_selection_views.xml",
        "wizard/wizard_duplicate_checker.xml",
        "data/cron.xml",
        "views/menu.xml",
        "security/security.xml"
    ],
    "assets": {},
    "installable": True,
    "application": True,
}
