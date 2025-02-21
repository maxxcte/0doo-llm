# LLM Thread Module

This Odoo module provides functionality for managing and interacting with threads in a Large Language Model (LLM) context. It includes components for chat threads, message lists, and composer views.

## Features

- **Chat Thread Management**: Create, update, and manage chat threads.
- **Message List**: Display and interact with messages in a thread.
- **Composer View**: Input and send messages within a thread.
- **Tool Integration**: Support for function calling and tools that allow LLM models to perform actions in Odoo.

## Installation

1. Clone the repository into your Odoo addons directory.
2. Install the module via the Odoo Apps menu.

## Usage

1. First, install and configure at least one LLM provider module (e.g., llm_openai, llm_anthropic, llm_ollama).
2. Configure the provider with appropriate API keys and settings.
3. Navigate to **LLM → Chat** menu item in your Odoo instance.
4. Click on "New Chat" to start a new conversation thread.
5. You can create multiple threads, view existing ones, and interact with messages.
6. If you have installed the llm_tool module, you can enable function calling capabilities that allow the AI to perform actions in Odoo, such as creating records, searching for information, or executing specific business logic.

## Dependencies

- Odoo 16.0 or later
- Python 3.8 or later

## Contributing

Contributions are welcome! Please follow the contribution guidelines in the repository.

## License

This module is licensed under the [MIT License](https://opensource.org/licenses/MIT).
