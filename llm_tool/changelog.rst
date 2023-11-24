16.0.1.0.1 (2025-04-08)
~~~~~~~~~~~~~~~~~~~~~~~

* [IMP] Improvements:
  * Added explicit type hints (`list[str]`, `list[list[Any]]`) to list fields in Pydantic models for `fields_inspector`, `record_unlinker`, and `record_updater` tools to improve schema validation and API compatibility.

16.0.1.0.0 (2025-03-06)
~~~~~~~~~~~~~~~~~~~~~~~

* [INIT] Initial release of the module with the following features:
  * LLM Tool Integration - Added ability to chat with LLM models using llm.tool implementations
  * Tool Implementations - Support for odoo_record_retriever and odoo_server_action tools
  * Tool Message Handling - Chat UI for tool messages with cog icon and display of tool arguments and results
