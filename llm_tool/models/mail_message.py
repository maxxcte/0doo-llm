from odoo import fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    tool_calls = fields.Text(
        string="LLM Tool Calls",
        help="JSON serialized list of tool calls made by the assistant in this message.",
        readonly=True,
        copy=False,
    )
    tool_call_id = fields.Char(
        string="LLM Tool Call ID",
        help="The unique ID of the tool call this message is a result for.",
        readonly=True,
        index=True,
        copy=False,
    )
    # Definition might be useful for displaying the request directly on the tool message
    tool_call_definition = fields.Text(
        string="LLM Tool Call Definition",
        help="JSON serialized definition of the tool call (type, function name, arguments). Copied from the request.",
        readonly=True,
        copy=False,
    )
    tool_call_result = fields.Text(
        string="LLM Tool Call Result",
        help="JSON serialized result returned by the tool execution (or error).",
        readonly=True,
        copy=False,
    )
