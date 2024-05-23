import json

from odoo import _, api, fields, models

from odoo.exceptions import UserError

from odoo.addons.llm_mail_message_subtypes.const import (
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
    LLM_USER_SUBTYPE_XMLID,
    LLM_ASSISTANT_SUBTYPE_XMLID,
)


class LLMThread(models.Model):
    _name = "llm.thread"
    _description = "LLM Chat Thread"
    _inherit = ["mail.thread"]
    _order = "write_date DESC"

    name = fields.Char(
        string="Title",
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        required=True,
        ondelete="restrict",
    )
    provider_id = fields.Many2one(
        "llm.provider",
        string="Provider",
        required=True,
        ondelete="restrict",
    )
    model_id = fields.Many2one(
        "llm.model",
        string="Model",
        required=True,
        domain="[('provider_id', '=', provider_id), ('model_use', 'in', ['chat', 'multimodal'])]",
        ondelete="restrict",
    )
    active = fields.Boolean(default=True)
    message_ids = fields.One2many(
        comodel_name="mail.message",
        inverse_name="res_id",
        string="Messages",
        domain=lambda self: [("model", "=", self._name)],
    )

    related_thread_model = fields.Char("Related Thread Model")
    related_thread_id = fields.Integer("Related Thread ID")

    tool_ids = fields.Many2many(
        "llm.tool",
        string="Available Tools",
        help="Tools that can be used by the LLM in this thread",
    )

    # TODO: need a way to lock this llm.thread if it is already looping

    @api.model_create_multi
    def create(self, vals_list):
        """Set default title if not provided"""
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = f"Chat with {self.model_id.name}"
        return super().create(vals_list)

    def create_new_message(self, **kwargs):
        self.ensure_one()
        Message = self.env['mail.message']
        # if subtype_xmlid is not provided or wrong,message_post automatically
        # uses the default subtype
        subtype_xmlid = kwargs.get('subtype_xmlid')
        author_id = kwargs.get('author_id')
        body = kwargs.get('body', '')
        email_from = Message.get_email_from(self.provider_id.name, self.model_id.name, subtype_xmlid, author_id, kwargs.get('tool_name'))
        post_vals = Message.build_post_vals(subtype_xmlid, body, author_id, email_from)
        message = self.message_post(**post_vals)
        extra_vals = Message.build_update_vals(
            subtype_xmlid,
            tool_call_id=kwargs.get('tool_call_id'),
            tool_calls=kwargs.get('tool_calls'),
            tool_call_definition=kwargs.get('tool_call_definition'),
            tool_call_result=kwargs.get('tool_call_result'),
        )
        if extra_vals:
            message.write(extra_vals)
        return message

    def _get_message_history_recordset(self, order='ASC', limit=None):
        """Get messages from the thread

        Args:
            limit: Optional limit on number of messages to retrieve

        Returns:
            mail.message recordset containing the messages
        """
        self.ensure_one()
        subtypes_to_fetch = [
            self.env.ref(LLM_USER_SUBTYPE_XMLID, raise_if_not_found=False),
            self.env.ref(LLM_ASSISTANT_SUBTYPE_XMLID, raise_if_not_found=False),
            self.env.ref(LLM_TOOL_RESULT_SUBTYPE_XMLID, raise_if_not_found=False),
        ]       
        subtype_ids = [st.id for st in subtypes_to_fetch if st]    
        order_clause = f"create_date {order}, id {order}"
        domain = [
            ("model", "=", self._name),
            ("res_id", "=", self.id),
            ("message_type", "=", "comment"),
            ("subtype_id", "in", subtype_ids),
        ]
        messages = self.env["mail.message"].search(
            domain, order=order_clause, limit=limit
        )
        return messages
    

    def _get_last_message_from_history(self):
        """Get the last message from the message history."""
        self.ensure_one()
        last_message = None
        result = self._get_message_history_recordset(order='DESC', limit=1)
        if result:
            last_message = result[0]
        if not last_message:
            raise UserError("No message found to process.")
        return last_message

    def _init_message(self, user_message_body):
        """Initialize first message: user input or history."""
        if user_message_body:
            return self.create_new_message(
                subtype_xmlid=LLM_USER_SUBTYPE_XMLID,
                body=user_message_body,
                author_id=self.env.user.partner_id.id,
            )
        return self._get_last_message_from_history()

    def _should_continue(self, last_message):
        """Whether to keep looping on the last_message."""
        if not last_message:
            return False
        if last_message.is_llm_user_message() or last_message.is_llm_tool_result_message():
            return True
        if last_message.is_llm_assistant_message() and last_message.tool_calls:
            return True
        return False

    def _next_step(self, last_message):
        """Dispatch to the next generator based on message type."""
        if last_message.is_llm_user_message() or last_message.is_llm_tool_result_message():
            return self._get_assistant_response()
        if last_message.is_llm_assistant_message() and last_message.tool_calls:
            return self._process_tool_calls(last_message)
        return last_message

    def generate(self, user_message_body):
        # orchestrate via hooks
        self.ensure_one()
        last = self._init_message(user_message_body)
        if user_message_body:
            yield {'type': 'message_create', 'message': last.message_format()[0]}
        while self._should_continue(last):
            last = yield from self._next_step(last)
        return last

    def _process_tool_calls(self, assistant_msg):
        self.ensure_one()
        defs = json.loads(assistant_msg.tool_calls or "[]")
        last_tool_msg = None
        for tool_def in defs:
            last_tool_msg = yield from self.env["mail.message"].stream_llm_tool_result(
                thread=self,
                tool_call_def=tool_def,
            )
        return last_tool_msg       

    def _get_assistant_response(self):
        self.ensure_one()
        message_history_rs = self._get_message_history_recordset()
        tool_rs = self.tool_ids
        stream_response = self.model_id.chat(
            messages=message_history_rs,
            tools=tool_rs,
            stream=True
        )
        assistant_msg = yield from self.env["mail.message"].stream_llm_response(
            self,
            stream_response,
            LLM_ASSISTANT_SUBTYPE_XMLID,
            placeholder_text="Thinking..."
        )

        return assistant_msg
        

    def _create_tool_response(self, tool_name, arguments_str, tool_call_id, result_data):
        """Create a standardized tool response structure."""
        return {
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": arguments_str,
            },
            "result": json.dumps(result_data),
        }

    def _execute_tool(self, tool_name, arguments_str, tool_call_id):
        """Execute a tool and return the result."""
        try:
            tool = self.env["llm.tool"].search([("name", "=", tool_name)], limit=1)
            if not tool:
                raise UserError(f"Tool '{tool_name}' not found")
            arguments = json.loads(arguments_str)
            result = tool.execute(arguments)
            return self._create_tool_response(tool_name, arguments_str, tool_call_id, result)
        except Exception as e:
            return self._create_tool_response(
                tool_name, arguments_str, tool_call_id, {"error": str(e)}
            )