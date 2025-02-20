# LiteLLM Proxy Integration for Odoo

This module integrates LiteLLM proxy with the Odoo LLM framework, providing access to multiple LLM providers through a single proxy.

## Features

- Connect to LiteLLM proxy with proper authentication
- Support for multiple LLM providers through a single endpoint
- Text generation capabilities
- Automatic model discovery
- Rate limiting and cost tracking through proxy

## Configuration

1. Install the module
2. Navigate to **LLM > Configuration > Providers**
3. Create a new provider and select "LiteLLM" as the provider type
4. Enter your LiteLLM proxy URL and API key (if required)
5. Click "Fetch Models" to import available models

## Current Status

This module is in an early stage of development. Basic functionality for connecting to LiteLLM proxy and generating text is implemented, but advanced features are still under development.

## Technical Details

This module extends the base LLM integration framework with LiteLLM-specific implementations:

- Implements the LiteLLM proxy client with proper authentication
- Provides model mapping between LiteLLM formats and Odoo LLM formats
- Handles basic error cases

## Dependencies

- llm (LLM Integration Base)

## License

LGPL-3
