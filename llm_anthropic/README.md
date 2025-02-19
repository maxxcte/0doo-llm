# Anthropic Provider for Odoo LLM Integration

This module integrates Anthropic's Claude API with the Odoo LLM framework, providing access to Claude models for text generation.

## Features

- Connect to Anthropic Claude API with proper authentication
- Support for Claude models (Claude 3 Opus, Sonnet, Haiku)
- Text generation capabilities
- Automatic model discovery

## Configuration

1. Install the module
2. Navigate to **LLM > Configuration > Providers**
3. Create a new provider and select "Anthropic" as the provider type
4. Enter your Anthropic API key
5. Click "Fetch Models" to import available models

## Current Status

This module is in an early stage of development. Basic functionality for connecting to Anthropic's API and generating text with Claude models is implemented, but advanced features are still under development.

## Technical Details

This module extends the base LLM integration framework with Anthropic-specific implementations:

- Implements the Anthropic API client with proper authentication
- Provides model mapping between Anthropic formats and Odoo LLM formats
- Handles basic error cases

## Dependencies

- llm (LLM Integration Base)

## License

LGPL-3
