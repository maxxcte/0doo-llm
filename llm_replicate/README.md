# Replicate Provider for Odoo LLM Integration

This module integrates Replicate's API with the Odoo LLM framework, providing access to a diverse range of AI models.

## Features

- Connect to Replicate API with proper authentication
- Support for various AI models hosted on Replicate
- Text generation capabilities
- Automatic model discovery

## Configuration

1. Install the module
2. Navigate to **LLM > Configuration > Providers**
3. Create a new provider and select "Replicate" as the provider type
4. Enter your Replicate API key
5. Click "Fetch Models" to import available models

## Current Status

This module is in an early stage of development. Basic functionality for connecting to Replicate's API and generating text with various models is implemented, but advanced features are still under development.

## Technical Details

This module extends the base LLM integration framework with Replicate-specific implementations:

- Implements the Replicate API client with proper authentication
- Provides model mapping between Replicate formats and Odoo LLM formats
- Handles basic error cases

## Dependencies

- llm (LLM Integration Base)

## License

LGPL-3
