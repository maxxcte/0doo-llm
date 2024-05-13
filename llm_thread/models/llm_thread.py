import json
import logging
import emoji
import markdown2

from odoo import _, api, fields, models

from odoo.exceptions import MissingError, UserError

from odoo.addons.llm_mail_message_subtypes.const import (
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
    LLM_USER_SUBTYPE_XMLID,
    LLM_ASSISTANT_SUBTYPE_XMLID,
)

_logger = logging.getLogger(__name__)


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
        """Save a message to the thread with support for tool messages"""
        self.ensure_one()
        subtype_xmlid = kwargs.get("subtype_xmlid")
        if not subtype_xmlid:
            raise ValueError("Subtype XML ID is required for create_new_message")

        try:
            # TODO: cache this subtype -> subtype id if possible
            subtype = self.env.ref(subtype_xmlid)
        except ValueError: # Catches if XML ID format is wrong or module not installed
            raise MissingError(f"Subtype with XML ID '{subtype_xmlid}' not found.")
        if not subtype.exists():
            raise MissingError(f"Subtype with XML ID '{subtype_xmlid}' not found.")

        body = emoji.demojize(kwargs.get("body"))

        email_from = False # Let Odoo handle default unless we override
        is_tool_result = subtype_xmlid == LLM_TOOL_RESULT_SUBTYPE_XMLID
        is_assistant = subtype_xmlid == LLM_ASSISTANT_SUBTYPE_XMLID
        author_id = kwargs.get("author_id")
        # Handle tool messages
        tool_call_id = kwargs.get("tool_call_id")
        tool_calls = kwargs.get("tool_calls")
        tool_name = kwargs.get("tool_name")
        tool_call_definition = kwargs.get("tool_call_definition")
        tool_call_result = kwargs.get("tool_call_result")

        if not author_id: # AI or System messages
            if is_tool_result:
                tool_name = kwargs.get('tool_name', 'Tool') # Get optional tool name
                email_from = f"{tool_name} <tool@{self.provider_id.name.lower().replace(' ', '')}.ai>"
            elif is_assistant:
                model_name = self.model_id.name or 'Assistant'
                provider_name = self.provider_id.name or 'provider'
                email_from = f"{model_name} <ai@{provider_name.lower().replace(' ', '')}.ai>"

        post_vals = {
            'body': body,
            'message_type': 'comment',
            'subtype_xmlid': subtype_xmlid,
            'author_id': author_id,
            'email_from': email_from or None,
            'partner_ids': [],
        }
        if is_assistant:
            extra_vals = {
                'tool_calls': tool_calls,
            }
        elif is_tool_result:
            extra_vals = {
                'tool_call_id': tool_call_id,
                'tool_call_definition': tool_call_definition,
                'tool_call_result': tool_call_result,
            }
        else:
            extra_vals = {}
        extra_vals = {k: v for k, v in extra_vals.items() if v is not None}

        message = self.message_post(**post_vals)

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

    def generate(self, user_message_body):
        """
        Orchestrates the LLM interaction cycle synchronously in a loop.
        """
        self.ensure_one()
        last_message = None
        if user_message_body:
            last_message = self.create_new_message(
                subtype_xmlid=LLM_USER_SUBTYPE_XMLID,
                body=user_message_body,
                author_id=self.env.user.partner_id.id,
            )
            yield {'type': 'message_create', 'message': last_message.message_format()[0]}
        else:
            last_message = self._get_last_message_from_history()

        while True:
            if not last_message:
                raise UserError("No message found to process.")
            
            if last_message.is_llm_user_message() or last_message.is_llm_tool_result_message():
                # Process user message or tool result, in both cases we get assistant_msg
                # some assistant message has tool_calls, some don't
                for ev in self._get_assistant_response():
                    if ev.get('type') == 'message_finalize':
                        last_message = self._event_to_message_obj(ev)
                    else:
                        yield ev
                continue
            
            if last_message.is_llm_assistant_message():
                if last_message.tool_calls:
                    for ev in self._process_tool_calls(last_message):
                        if ev.get('type') == 'message_finalize':
                            # catch and keep track of last_message, don't yield it
                            last_message = self._event_to_message_obj(ev)
                        yield ev
                    continue
                else:
                    break
        
    def _process_tool_calls(self, assistant_msg):
        self.ensure_one()
        if assistant_msg and assistant_msg.tool_calls:
            # Load validated definitions from the saved field
            tool_call_definitions = json.loads(assistant_msg.tool_calls or '[]')
            last_tool_msg = None
            for tool_call_def in tool_call_definitions:
                tool_call_id = tool_call_def.get('id')
                tool_function = tool_call_def.get('function', {})
                tool_name = tool_function.get('name', 'unknown_tool')
                if not tool_call_id or not tool_name:
                    continue
                
                for ev in self._execute_tool_call(tool_call_def):
                    current_tool_msg = self._event_to_message_obj(ev)
                    if current_tool_msg:
                        # Keep the object to keep track of last tool result
                        last_tool_msg = current_tool_msg
                        # dipsatch it for frontend it update for each tool result
                        yield {'type': 'message_update', 'message': last_tool_msg.message_format()[0]}
                    else:
                        yield ev
                
            yield {'type': 'message_finalize', 'message': last_tool_msg}

    def _event_to_message_obj(self, event):
        self.ensure_one()
        if event.get('type') == 'message_finalize' and event.get('message'):
            return event['message']
        else:
            return None
        

    def _get_assistant_response(self):
        self.ensure_one()
        message_history_rs = self._get_message_history_recordset()
        tool_rs = self.tool_ids
        stream_response = self.model_id.chat(
            messages=message_history_rs,
            tools=tool_rs,
            stream=True
        )
        assistant_msg = None
        
        accumulated_content = ""
        received_tool_calls = []

        for chunk in stream_response:
            if assistant_msg is None and (chunk.get('content') or chunk.get('tool_calls')):
                assistant_msg = self.create_new_message(
                    subtype_xmlid=LLM_ASSISTANT_SUBTYPE_XMLID,
                    body="Thinking...", # Start empty
                    author_id=False
                )
                assistant_msg_payload = assistant_msg.message_format()[0]
                yield {'type': 'message_create', 'message': assistant_msg_payload}

            if chunk.get('content'):
                content_chunk = chunk.get('content')
                accumulated_content += content_chunk
                updated_body = markdown2.markdown(accumulated_content)
                updated_payload = assistant_msg_payload.copy()
                updated_payload['body'] = updated_body
                yield {'type': 'message_chunk', 'message': updated_payload}

            if chunk.get('tool_calls'):
                calls = chunk.get('tool_calls')
                if isinstance(calls, list):
                    valid_calls = [c for c in calls if isinstance(c, dict) and c.get('id') and c.get('function')]
                    received_tool_calls.extend(valid_calls)
                    if len(valid_calls) != len(calls):
                        _logger.warning(f"Thread {self.id}: Invalid tool calls received: {calls}")
                else: 
                    _logger.warning(f"Thread {self.id}: Received non-list tool_calls: {calls}")

            if chunk.get('error'):
                yield {'type': 'error', 'error': chunk['error']}
                return
        
        update_vals = {}
        if accumulated_content:
            update_vals['body'] = markdown2.markdown(accumulated_content)
        if received_tool_calls:
            update_vals['tool_calls'] = json.dumps(received_tool_calls)

        if accumulated_content or received_tool_calls:
            assistant_msg.write(update_vals)

        yield {'type': 'message_update', 'message': assistant_msg.message_format()[0]}
        # Always send finalize event with direct object, but top generator would not dispatch it
        yield {'type': 'message_finalize', 'message': assistant_msg}

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
        """Execute a tool and return the result

        Args:
            tool_name: Name of the tool to execute
            arguments_str: JSON string of arguments for the tool
            tool_call_id: ID of the tool call

        Returns:
            Dictionary with tool execution result
        """

        tool = self.env["llm.tool"].search([("name", "=", tool_name)], limit=1)

        if not tool:
            raise UserError(f"Tool '{tool_name}' not found")

        try:
            arguments = json.loads(arguments_str)
            result = tool.execute(arguments)
            return self._create_tool_response(tool_name, arguments_str, tool_call_id, result)
        except Exception as e:
            return self._create_tool_response(
                tool_name, arguments_str, tool_call_id, {"error": str(e)}
            )

    def _execute_tool_call(self, tool_call_def):
        """Executes a single tool call, creates tool message, and streams updates."""
        tool_msg = None
        tool_call_id = tool_call_def.get('id')
        tool_function = tool_call_def.get('function', {})
        tool_name = tool_function.get('name', 'unknown_tool')

        if not tool_call_id or not tool_name:
            _logger.warning(f"Thread {self.id}: Skipping tool call due to missing id or name: {tool_call_def}")
            yield None

        try:
            # 1. Create Placeholder Message
            tool_msg = self.create_new_message(
                subtype_xmlid=LLM_TOOL_RESULT_SUBTYPE_XMLID,
                tool_call_id=tool_call_id,
                tool_call_definition=json.dumps(tool_call_def),
                tool_call_result=None,
                body=f"Executing: {tool_name}...",
                author_id=False,
                tool_name=tool_name
            )

            tool_msg_payload = tool_msg.message_format()[0]
            yield {'type': 'message_create', 'message': tool_msg_payload}
            
            args_str = tool_function.get('arguments')
            tool_response_dict = self._execute_tool(tool_name, args_str, tool_call_id)

            # 4. Process Result & Update Message
            result_str = tool_response_dict.get("result", json.dumps({"error": "Tool execution failed to return a 'result' key"}))
            final_body = f"Result for {tool_name}"
            tool_msg_vals = {
                'tool_call_result': result_str,
                'body': final_body
            }
            tool_msg.write(tool_msg_vals)
            
            yield {'type': 'message_finalize', 'message': tool_msg}

        except Exception as tool_err:
            error_msg = f"Error processing tool call {tool_call_id} ({tool_name}): {tool_err}"
            tool_msg.write({'tool_call_result': json.dumps({'error': error_msg}), 'body': f"Error executing {tool_name}"})
            yield {'type': 'message_finalize', 'message': tool_msg}
