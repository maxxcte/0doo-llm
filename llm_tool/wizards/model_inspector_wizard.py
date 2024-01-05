# -*- coding: utf-8 -*-
import inspect
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ModelInspectorWizard(models.TransientModel):
    _name = "llm_tool.model.inspector.wizard"
    _description = "Model Inspector Wizard"

    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        help="Select the Odoo model you want to inspect.",
        # No specific ondelete needed as ir.model records are protected
    )
    include_private = fields.Boolean(
        string="Include Private Methods",
        default=True,
        help="Check this to include methods starting with '_'",
    )
    method_lines = fields.One2many(
        "llm_tool.model.inspector.wizard.line",
        "wizard_id",
        string="Methods",
        readonly=True,
    )

    def action_inspect_model(self):
        self.ensure_one()
        self.method_lines.unlink()  # Clear previous results

        if not self.model_id:
            raise UserError(_("Please select a model to inspect."))

        model_technical_name = self.model_id.model # Get technical name here
        try:
            Model = self.env[model_technical_name]
        except KeyError:
            raise UserError(_("Model '%s' not found in Odoo environment.") % model_technical_name)

        lines_vals = []
        inspected_methods = set() # Keep track to avoid duplicates from inheritance

        # Iterate through the MRO (Method Resolution Order) to catch inherited methods correctly
        for cls in Model.__class__.__mro__:
            # Limit inspection to Odoo models (avoiding object, etc.)
            if not issubclass(cls, models.BaseModel):
                continue
                
            for name, member in inspect.getmembers(cls):
                # Avoid duplicates already processed from a subclass
                if name in inspected_methods:
                    continue
                    
                # Filter 1: Must be callable (function, method, etc.)
                if not callable(member):
                    continue

                # Filter 2: Handle private methods based on flag
                is_private = name.startswith("_")
                if is_private and not self.include_private:
                    continue
                    
                # Filter 3: Avoid common non-method Python internals 
                if name in ('__doc__', '__init__', '__module__', '__new__', '__qualname__', '__slots__', '__weakref__'):
                    continue
                    
                # Add to inspected set
                inspected_methods.add(name)

                # Get details
                details = self._extract_method_details(member, name)
                lines_vals.append(details)

        # Sort lines alphabetically by method name for consistency
        lines_vals.sort(key=lambda x: x['name'])
        
        # Create the line records
        self.method_lines = [(0, 0, vals) for vals in lines_vals]

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def _extract_method_details(self, method_obj, name):
        """Helper function to extract details for a single method object."""
        details = {
            "name": name,
            "docstring": "",
            "signature": "(Could not determine signature)",
            "method_type": "unknown", # instance, model, static
            "decorators": "",
        }

        # a) Get Docstring
        try:
            doc = inspect.getdoc(method_obj)
            if doc:
                details["docstring"] = doc.strip()
        except Exception as e:
            _logger.debug("Could not get docstring for %s: %s", name, e)

        # b) Get Signature
        try:
            sig = inspect.signature(method_obj)
            details["signature"] = str(sig)
        except ValueError:
            details["signature"] = "(Signature inspection not supported)"
        except TypeError: # Handle cases like built-in methods or slots
            details["signature"] = "(Signature inspection not applicable)"
        except Exception as e:
            _logger.warning("Could not get signature for %s: %s", name, e)
            
        # c/d) Determine Type and Decorators (Odoo specific checks)
        decorators_list = []
        if hasattr(method_obj, "_api_model"): 
            details["method_type"] = "model"
            decorators_list.append("@api.model")
        elif isinstance(method_obj, staticmethod) or getattr(method_obj, "_is_static", False):
            details["method_type"] = "static"
            decorators_list.append("@staticmethod")
        elif isinstance(method_obj, classmethod):
            details["method_type"] = "class"
            decorators_list.append("@classmethod")
        else:
            # Assume instance method if not otherwise identified
            # Check if it's bound to the class via descriptor protocol typical for instance methods
            if hasattr(method_obj, '__get__') and not isinstance(method_obj, (staticmethod, classmethod)):
                 details["method_type"] = "instance"
            # Could be a simple function attached to the class namespace
            elif inspect.isfunction(method_obj):
                details["method_type"] = "function"
        
        # Add other known Odoo decorators
        if hasattr(method_obj, "_api_depends"):
             # Attempt to get actual dependencies, otherwise use placeholder
            try:
                deps = getattr(method_obj, "_api_depends_args", "...")
                decorators_list.append(f"@api.depends({deps})")
            except Exception:
                 decorators_list.append("@api.depends(...)")
        if hasattr(method_obj, "_returns_model"):
            decorators_list.append(f"@api.returns('{getattr(method_obj, '_returns_model')}')")
        if hasattr(method_obj, "_api_constrains"):
             try:
                cons = getattr(method_obj, "_api_constrains_args", "...")
                decorators_list.append(f"@api.constrains({cons})")
             except Exception:
                decorators_list.append("@api.constrains(...)")
        if hasattr(method_obj, "_api_onchange"):
             try:
                onch = getattr(method_obj, "_api_onchange_args", "...")
                decorators_list.append(f"@api.onchange({onch})")
             except Exception:
                decorators_list.append("@api.onchange(...)")

        details["decorators"] = ", ".join(decorators_list)

        return details


class ModelInspectorWizardLine(models.TransientModel):
    _name = "llm_tool.model.inspector.wizard.line"
    _description = "Model Inspector Wizard Line"
    _order = "name asc" # Ensure alphabetical order in the view

    wizard_id = fields.Many2one(
        "llm_tool.model.inspector.wizard", string="Wizard", required=True, ondelete="cascade"
    )
    name = fields.Char(string="Method Name", readonly=True)
    signature = fields.Char(string="Signature", readonly=True)
    docstring = fields.Text(string="Docstring", readonly=True)
    method_type = fields.Char(string="Type", readonly=True) # e.g., instance, model, static
    decorators = fields.Char(string="Decorators", readonly=True)
