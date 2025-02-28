# LLM Assistant

This Odoo module provides AI assistant capabilities for the LLM integration, allowing for specialized AI assistants with dedicated tools and configurations.

## Features

- **Assistant Management**: Create and configure AI assistants with specific roles and goals
- **Tool Integration**: Assign preferred tools to each assistant for specialized capabilities
- **System Prompt Generation**: Automatically generate system prompts based on assistant configuration
- **Thread Integration**: Attach assistants to chat threads for consistent behavior
- **UI Integration**: Seamlessly switch between assistants in the chat interface

## Installation

1. Clone the repository into your Odoo addons directory.
2. Install the module via the Odoo Apps menu.

## Configuration

1. Navigate to LLM > Configuration > Assistants
2. Create new assistants with specific providers and models
3. Configure tools and system prompts for each assistant
4. Assign assistants to specific user groups if needed

## Usage

### Creating an Assistant

1. Go to LLM > Configuration > Assistants
2. Click "Create" to add a new assistant
3. Configure the assistant with a name, provider, model, and prompt template
4. Add preferred tools that the assistant can use
5. Save the assistant configuration

### Prompt Template for Assistants

The module uses a structured prompt template with the following variables:

- **role**: Defines the assistant's specific role (e.g., "Assistant Creator")
- **goal**: Describes the primary objective of the assistant
- **background**: Provides context and knowledge the assistant should have
- **instructions**: Detailed step-by-step guidance for the assistant
- **footer**: Additional important notes or reminders

### Pre-configured Assistants

The module includes the following pre-configured assistants:

1. **Assistant Creator**: Guides users through creating and configuring specialized AI assistants in Odoo, ensuring all required fields are properly set and appropriate tools are attached.

2. **Website Builder**: Helps update website content, structure, and functionality within the Odoo system, implementing changes safely and methodically.

### Using an Assistant in Chat

1. Open a chat thread from LLM > Threads
2. Select an assistant from the dropdown in the chat header
3. The assistant's configuration (provider, model, tools) will be applied to the thread
4. Start chatting with the configured assistant

## Dependencies

- Odoo 16.0 or later
- Python 3.8 or later
- Required Odoo modules:
  - base
  - mail
  - web
  - llm
  - llm_thread
  - llm_tool
  - llm_prompt

## Contributing

Contributions are welcome! Please follow the contribution guidelines in the repository.

## License

This module is licensed under the LGPL-3 license.
