# LLM Tool Module for Odoo 16

This module extends the LLM integration in Odoo by adding support for tools that can be used by LLM models to interact with the Odoo system.

## Features

- Define tools with JSON schema for parameters
- Uses the dispatch pattern for tool implementations
- Includes a record retriever tool for accessing Odoo data
- Implements OpenAI's tool calling API
- Supports streaming responses with tool execution

## Models

### llm.tool

Defines tools that LLM models can use to interact with Odoo:

- **name**: Tool name (must match what the LLM will call)
- **description**: Description of what the tool does
- **service**: The service that implements this tool
- **schema**: JSON Schema for the tool parameters
- **default**: Whether this tool should be included by default

### llm.thread (extended)

Extends the existing thread model to support tools:

- **tool_ids**: Many2many field linking to available tools for the thread

## Implementation

The module follows Odoo's best practices:

1. Uses the dispatch pattern for extensibility
2. Properly handles streaming responses
3. Provides good error handling and logging
4. Includes security access controls

## Usage Example

```python
# Get a thread with tools
thread = env['llm.thread'].browse(thread_id)

# Add a specific tool to the thread
record_retriever = env['llm.tool'].search([('name', '=', 'retrieve_records')])
thread.write({'tool_ids': [(4, record_retriever.id)]})

# Get a response that may use tools
for response in thread.get_assistant_response():
    # Handle the response
    print(response)
```

## Tool Implementation

Adding a new tool involves:

1. Creating a new tool record
2. Implementing the service method (e.g., `my_service_execute`)
3. Adding the service to the selection list

## Security

The module includes security access control rules:

- Regular users can read tools
- System administrators can create, update, and delete tools
