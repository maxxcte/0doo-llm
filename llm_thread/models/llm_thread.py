import json
import logging
from datetime import datetime
import emoji
import markdown2

from odoo import _, api, fields, models

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

from odoo.addons.llm_mail_message_subtypes.const import (
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
    LLM_USER_SUBTYPE_XMLID,
    LLM_ASSISTANT_SUBTYPE_XMLID,
)

_logger = logging.getLogger(__name__)


class LLMThread(models.Model):
    _name = "llm.thread"
    _description = "LLM Chat Thread"
    _inherit = ["mail.thread", "bus.immediate.send.mixin"]
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

    llm_thread_state = fields.Selection(
        [
            ('idle', 'Idle'),
            ('streaming', 'Processing'),
        ],
        string="Processing State",
        default='idle',
        readonly=True,
        required=True,
        copy=False,
        tracking=True,
        help="Reflects the backend processing state of the thread. 'Processing' means the system is working on a response.")

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
            subtype = self.env.ref(subtype_xmlid)
        except ValueError: # Catches if XML ID format is wrong or module not installed
             _logger.error(f"Invalid XML ID format or module missing for subtype: {subtype_xmlid}")
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

        message_payload = message.message_format()[0]
        self._notify_message_insert(message_payload)

        return message

    def _notify_message_insert(self, message_payload):
        self.ensure_one()
        partner_id = self.env.user.partner_id.id
        channel = (self.env.cr.dbname, 'res.partner', partner_id)
        self._sendone_immediately(channel, 'mail.message/insert_custom', message_payload)
        _logger.info(f"Message inserted: {datetime.now()}")
    
    def _notify_message_update(self, message):
        """Sends updated message data immediately via bus."""
        self.ensure_one() # Context: called from thread
        if not message or not message.exists():
             return
        message_payload = message.message_format()[0] # Get latest data
        partner_id = self.env.user.partner_id.id
        channel = (self.env.cr.dbname, 'res.partner', partner_id) # Send to partner
        self._sendone_immediately(channel, 'mail.message/update_custom', message_payload)

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
        domain = [
            ("model", "=", self._name),
            ("res_id", "=", self.id),
            ("message_type", "=", "comment"),
            ("subtype_id", "in", subtype_ids),
        ]
        messages = self.env["mail.message"].search(
            domain, order="create_date {order}", limit=limit
        )
        return messages
    

    def start_thread_loop(self, user_message_body):
        """
        Orchestrates the LLM interaction cycle synchronously in a loop.
        """
        self.ensure_one()
        if self.llm_thread_state == 'streaming' and user_message_body is not None:
            raise UserError("Thread is already processing, cannot process new request.")

        self.write({'llm_thread_state': 'streaming'})
        
        last_message = None
        if user_message_body is not None:
            last_message = self.create_new_message(
                subtype_xmlid=LLM_USER_SUBTYPE_XMLID,
                body=user_message_body,
                author_id=self.env.user.partner_id.id,
            )
        
        if not last_message:
            last_message_in_history = self._get_message_history_recordset(order='DESC', limit=1)
            if last_message_in_history:
                last_message = last_message_in_history[0]
        
        if not last_message:
            raise UserError("No message found to process.")

        current_iteration = 0
        MAX_ITERATION = 10



        while current_iteration < MAX_ITERATION:
            current_iteration += 1

            if not last_message:
                # fail-safe check
                raise UserError("No message found to process.")
            
            if last_message.is_llm_user_message() or last_message.is_llm_tool_result_message():
                # Process user message or tool result
                assistant_msg = self._start_streaming()
                last_message = assistant_msg
                continue
            
            if last_message.is_llm_assistant_message():
                if last_message.tool_calls:
                    # Process tool calls
                    last_tool_msg = self._process_tool_calls(last_message)
                    last_message = last_tool_msg
                    continue
                else:
                    break
        
        self.write({'llm_thread_state': 'idle'})
    
    def _process_tool_calls(self, assistant_msg):
        self.ensure_one()
        if assistant_msg and assistant_msg.tool_calls:
            # Load validated definitions from the saved field
            tool_call_definitions = json.loads(assistant_msg.tool_calls or '[]')
            last_tool_msg = None
            for tool_call_def in tool_call_definitions:
                tool_msg = None
                tool_stream_id = None
                tool_call_id = tool_call_def.get('id')
                tool_function = tool_call_def.get('function', {})
                tool_name = tool_function.get('name', 'unknown_tool')
                if not tool_call_id or not tool_name:
                    continue
                try:
                    # 1. Create Tool Result Message placeholder using create_new_message
                    # Pass necessary fields for the write() call within create_new_message
                    tool_msg = self.create_new_message(
                        subtype_xmlid=LLM_TOOL_RESULT_SUBTYPE_XMLID,
                        tool_call_id=tool_call_id,
                        tool_call_definition=json.dumps(tool_call_def), # Store definition
                        tool_call_result=None, # Result is not known yet
                        body=f"Executing: {tool_name}...", # Initial body
                        author_id=False,
                        tool_name=tool_name # For email_from
                    )
                    # 2. Signal Start of Execution
                    tool_stream_id = tool_msg.stream_start(
                        initial_data={'tool_call_id': tool_call_id, 'definition': tool_call_def}
                    )
                    _logger.info(f"Thread {self.id}: Tool msg {tool_msg.id} created, stream {tool_stream_id} started for tool {tool_call_id}.")

                    # 3. Execute Tool
                    args_str = tool_function.get('arguments')
                    # Pass tool_call_id as required by your _execute_tool signature
                    tool_response_dict = self._execute_tool(tool_name, args_str, tool_call_id)

                    # --- Extract Result/Error from the Structured Response ---
                    result_str = tool_response_dict.get("result", json.dumps({"error": "Tool execution failed to produce result"}))
                    execution_error = None
                    error_flag = False
                    try:
                        # Parse the inner 'result' JSON string to check for the error structure
                        parsed_result_data = json.loads(result_str)
                        if isinstance(parsed_result_data, dict) and 'error' in parsed_result_data:
                            execution_error = parsed_result_data['error']
                            error_flag = True
                    except (json.JSONDecodeError, TypeError):
                        # If result_str isn't valid JSON or not a dict, assume it's valid (but log)
                            _logger.warning(f"Tool {tool_name} result string was not valid JSON or dictionary: {result_str}. Assuming success content.")
                            error_flag = False # Treat non-error-structure as success content
                    # --- End Result/Error Extraction ---

                    final_body = f"{'Error' if error_flag else 'Result'} for {tool_name}"

                    # 4. Update Tool Result Message with the result JSON string
                    tool_msg.write({
                        'tool_call_result': result_str, # Store the JSON string from the 'result' key
                        'body': final_body
                    })

                    # 5. Signal Done for this tool's execution stream
                    tool_msg.stream_done(
                        tool_stream_id,
                        final_data={'message': tool_msg.message_format()[0]}, # Send final message state
                        error=tool_result_dict.get('error') if error_flag else None
                    )
                    self._notify_message_update(tool_msg)
                    last_tool_msg = tool_msg

                except Exception as tool_err:
                    error_msg = f"Error processing tool call {tool_call_id} ({tool_name}): {tool_err}"
                    _logger.exception(error_msg)
                    if tool_msg and tool_stream_id:
                        tool_msg.stream_done(tool_stream_id, error=error_msg)
                    if tool_msg: # Try to update message with error state
                        try: 
                            tool_msg.write({'tool_call_result': json.dumps({'error': error_msg}), 'body': f"Error: {tool_name}"})
                            self._notify_message_update(tool_msg)
                            last_tool_msg = tool_msg
                        except Exception: 
                            pass
                    raise UserError(_("An error occurred while executing tool '%(tool_name)s': %(error)s", tool_name=tool_name, error=tool_err))
            return last_tool_msg
                
    def _start_streaming(self):
        self.ensure_one()
        message_history_rs = self._get_message_history_recordset()
        tool_rs = self.tool_ids

        stream_response = self.model_id.chat(
                messages=message_history_rs,
                tools=tool_rs,
                stream=True
            )
        assistant_msg = None
        assistant_stream_id = None
        # 4. Consume Stream & Handle Assistant Message
        accumulated_content = ""
        received_tool_calls = [] # List to store tool call definitions from LLM

        for chunk in stream_response:
            if assistant_msg is None and (chunk.get('content') or chunk.get('tool_calls')):
                assistant_msg = self.create_new_message(
                    subtype_xmlid=LLM_ASSISTANT_SUBTYPE_XMLID,
                    body="Thinking...", # Start empty
                    author_id=False
                )
                assistant_stream_id = assistant_msg.stream_start(
                    initial_data={'stream_type': 'llm_assistant_response'}
                )

            # Process content chunks
            if assistant_stream_id and chunk.get('content'):
                content_chunk = chunk.get('content')
                accumulated_content += content_chunk
                assistant_msg.stream_chunk(assistant_stream_id, content_chunk)

            # Process tool call definitions
            if chunk.get('tool_calls'):
                calls = chunk.get('tool_calls')
                if isinstance(calls, list):
                    valid_calls = [c for c in calls if isinstance(c, dict) and c.get('id') and c.get('function')]
                    received_tool_calls.extend(valid_calls)
                    if len(valid_calls) != len(calls):
                        _logger.warning(f"Thread {self.id}: Invalid tool calls received: {calls}")
                else: 
                    _logger.warning(f"Thread {self.id}: Received non-list tool_calls: {calls}")

            # Handle error directly from stream chunk
            if chunk.get('error'):
                error_msg = f"LLM Provider stream error: {chunk['error']}"
                _logger.error(f"{error_msg} for Thread {self.id}")
                if assistant_msg and assistant_stream_id:
                    assistant_msg.stream_done(assistant_stream_id, error=error_msg)
                raise UserError(_("Error from Language Model: %s", chunk['error']))

        # 5. Finalize Assistant Message Stream and Update Record
        if assistant_stream_id:
            assistant_msg.stream_done(assistant_stream_id)
        
        update_vals = {'body': markdown2.markdown(accumulated_content)}
        if received_tool_calls:
            update_vals['tool_calls'] = json.dumps(received_tool_calls) # Save validated JSON
        if accumulated_content or received_tool_calls: # Check if update needed
            assistant_msg.write(update_vals)
            self._notify_message_update(assistant_msg)
        
        return assistant_msg

    def _create_tool_response(self, tool_name, arguments_str, tool_call_id, result_data):
        """Create a standardized tool response structure

        Args:
            tool_name: Name of the tool
            arguments_str: JSON string of arguments
            tool_call_id: ID of the tool call
            result_data: Result data to include (will be JSON serialized)

        Returns:
            Dictionary with standardized tool response format
        """
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
            _logger.error(f"Tool '{tool_name}' not found")
            return self._create_tool_response(
                tool_name,
                arguments_str,
                tool_call_id,
                {"error": f"Tool '{tool_name}' not found"},
            )

        try:
            arguments = json.loads(arguments_str)
            result = tool.execute(arguments)
            return self._create_tool_response(tool_name, arguments_str, tool_call_id, result)
        except Exception as e:
            _logger.exception(f"Error executing tool {tool_name}: {str(e)}")
            return self._create_tool_response(
                tool_name, arguments_str, tool_call_id, {"error": str(e)}
            )
