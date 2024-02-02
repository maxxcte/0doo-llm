# -*- coding: utf-8 -*-
{
    'name': 'Mail Message Streaming Events',
    'version': '16.0.1.0.0',
    'category': 'Discuss',
    'summary': 'Adds methods to mail.message for sending streaming bus events.',
    'description': """
Adds stream_start, stream_chunk, and stream_done methods directly to the
mail.message model to facilitate sending standardized streaming events
via the Odoo Bus related to specific messages.

This allows features like LLM responses to signal their progress consistently.
    """,
    'depends': [
        'bus',
        'mail',
    ],
    'author': 'Apexive Solutions LLC',
    'website': 'https://github.com/apexive/odoo-llm',
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}