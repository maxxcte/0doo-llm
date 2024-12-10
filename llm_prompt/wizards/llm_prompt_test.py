from odoo import fields, models


class LLMPromptTest(models.TransientModel):
    _name = "llm.prompt.test"
    _description = "LLM Prompt Test Wizard"

    prompt_id = fields.Many2one(
        "llm.prompt",
        string="Prompt",
        required=True,
        readonly=True,
    )
    messages = fields.Text(
        string="Messages",
        readonly=True,
        help="Generated messages from the prompt",
    )
