# LLM Resource

This Odoo module provides base document resource management for LLM modules, enabling Retrieval Augmented Generation (RAG) capabilities.

## Features

- **Resource Management**: Base document resource model for tracking and managing various document types
- **Flexible Retrieval**: Extensible retrieval interfaces for different content sources
- **Content Parsing**: Intelligent parsing of various content types into markdown format
- **HTTP Retrieval**: Built-in support for retrieving content from external URLs
- **Process Pipeline**: Structured workflow for retrieving, parsing, and managing resources

## Installation

1. Clone the repository into your Odoo addons directory.
2. Install the module via the Odoo Apps menu.

## Configuration

No special configuration is needed after installation. The module will be available for use by other LLM modules.

## Usage

### Creating Resources

Resources can be created from various sources:

1. From Odoo records using the model and record ID
2. From external URLs using the HTTP retriever
3. Programmatically through the API

### Processing Resources

Resources go through a defined processing pipeline:

1. **Retrieval**: Content is retrieved from the source (draft → retrieved)
2. **Parsing**: Content is parsed into markdown format (retrieved → parsed)

### Extending for Custom Models

To make your custom models compatible with LLM Resource:

1. Implement the `llm_get_retrieval_details` method to provide retrieval information
2. Optionally implement `llm_get_fields` to customize field extraction

```python
def llm_get_retrieval_details(self):
    """Return retrieval details for this record"""
    return {
        "type": "url",  # or other type
        "url": self.external_url,
        # other details as needed
    }
```

## Dependencies

- Odoo 16.0 or later
- Python 3.8 or later
- Python libraries:
  - requests
  - markdownify

## Contributing

Contributions are welcome! Please follow the contribution guidelines in the repository.

## License

This module is licensed under the LGPL-3 license.
