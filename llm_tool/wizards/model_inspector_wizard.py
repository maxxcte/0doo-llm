# -*- coding: utf-8 -*-
import inspect
import os
import logging
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ModelInspectorWizard(models.TransientModel):
    _name = 'model.inspector.wizard'
    _description = 'Model Inspector Wizard'

    model_name = fields.Char(string='Model Name', required=True)
    method_info = fields.Text(string='Method Information', readonly=True)
    file_paths = fields.Text(string='Source Files', readonly=True)
    selected_file_path = fields.Char(string='File Path to View')
    file_content = fields.Text(string='File Content', readonly=True)
    state = fields.Selection([
        ('start', 'Start'),
        ('inspected', 'Inspected'),
        ('file_view', 'File Viewed'),
    ], default='start', readonly=True)

    @api.model
    def _get_available_models(self):
        # Helper to potentially get a list of models, though not used in this simple version
        return [(name, name) for name in self.env.registry.keys()]

    def action_inspect_model(self):
        self.ensure_one()
        if not self.model_name:
            raise UserError(_("Please enter a model name."))

        try:
            model_obj = self.env[self.model_name]
        except KeyError:
            raise UserError(_("Model '%s' not found in the registry.") % self.model_name)

        methods = []
        files = set() # Use a set to store unique file paths

        # Inspect methods directly defined or overridden in the final class
        for name, member in inspect.getmembers(model_obj.__class__):
            if inspect.isfunction(member) or inspect.ismethod(member):
                docstring = inspect.getdoc(member) or "No description."
                signature = "N/A"
                source_file = "N/A"
                try:
                    sig = inspect.signature(member)
                    signature = str(sig)
                except (ValueError, TypeError):
                    pass # Cannot get signature
                try:
                    file_path = inspect.getsourcefile(member)
                    if file_path and os.path.exists(file_path):
                         # Store absolute path for later reading
                        files.add(os.path.abspath(file_path))
                        source_file = os.path.relpath(file_path) # Display relative path if possible
                except (OSError, TypeError):
                     pass # Cannot get source file

                methods.append(f"- {name}{signature}: {docstring} (Defined in: {source_file})")

        method_output = "\n".join(methods) if methods else "No specific methods found (check inherited methods)."
        file_output = "\n".join(sorted(list(files))) if files else "No source files found (might be built-in or only inherited)."

        self.write({
            'method_info': method_output,
            'file_paths': file_output,
            'state': 'inspected',
            'selected_file_path': '', # Clear previous selection
            'file_content': '',       # Clear previous content
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_view_file(self):
        self.ensure_one()
        if not self.selected_file_path:
            raise UserError(_("Please enter a file path from the list above to view."))

        # Basic security check: ensure the path is within the addons paths
        # This is NOT foolproof, but a basic sanity check for research
        allowed_paths_str = tools.config['addons_path']
        allowed_paths = [os.path.abspath(p) for p in allowed_paths_str.split(',')]

        absolute_path = os.path.abspath(self.selected_file_path)

        is_allowed = False
        for addons_path in allowed_paths:
            if os.path.commonpath([absolute_path, addons_path]) == addons_path:
                 is_allowed = True
                 break

        if not is_allowed or not os.path.exists(absolute_path) or not os.path.isfile(absolute_path):
             raise UserError(_("Invalid or disallowed file path: %s") % self.selected_file_path)

        try:
            with open(absolute_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.write({
                'file_content': content,
                'state': 'file_view',
            })
        except Exception as e:
            _logger.error("Error reading file %s: %s", absolute_path, e)
            raise UserError(_("Could not read file content: %s") % e)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_reset(self):
        self.write({
            'model_name': '',
            'method_info': '',
            'file_paths': '',
            'selected_file_path': '',
            'file_content': '',
            'state': 'start',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
