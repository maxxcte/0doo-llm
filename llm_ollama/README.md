# Ollama Provider for Odoo LLM Integration

This module integrates Ollama with the Odoo LLM framework, providing access to locally deployed open-source models.

## Features

- Connect to Ollama with proper configuration
- Support for various open-source models (Llama, Mistral, Vicuna, etc.)
- Text generation capabilities
- Function calling support
- Automatic model discovery
- Local deployment for privacy and control

## Configuration

1. Install the module
2. Set up Ollama on your server or local machine
3. Navigate to **LLM > Configuration > Providers**
4. Create a new provider and select "Ollama" as the provider type
5. Enter your Ollama server URL (default: http://localhost:11434)
6. Click "Fetch Models" to import available models

## Technical Details

This module extends the base LLM integration framework with Ollama-specific implementations:

- Implements the Ollama API client with proper configuration
- Provides model mapping between Ollama formats and Odoo LLM formats
- Supports function calling capabilities
- Handles streaming responses

## Dependencies

- llm (LLM Integration Base)
- llm_tool (LLM Tool Support)
- llm_mail_message_subtypes

## License

LGPL-3
