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

        # b) Get Detailed Signature
        try:
            sig = inspect.signature(method_obj)
            param_parts = []
            parameter_kinds = inspect.Parameter # Cache for easier access

            # Detect if positional-only or keyword-only separators are needed
            has_positional_only = any(p.kind == parameter_kinds.POSITIONAL_ONLY for p in sig.parameters.values())
            has_keyword_only = any(p.kind == parameter_kinds.KEYWORD_ONLY for p in sig.parameters.values())
            added_var_positional_marker = False # Track if '*' from *args was added

            for i, param in enumerate(sig.parameters.values()):
                part = param.name
                
                # 1. Handle Kind Prefixes/Separators
                if param.kind == parameter_kinds.VAR_POSITIONAL:
                    part = f"*{part}"
                    added_var_positional_marker = True
                elif param.kind == parameter_kinds.VAR_KEYWORD:
                    part = f"**{part}"
                elif param.kind == parameter_kinds.KEYWORD_ONLY:
                    # Add '*' separator if not already added by VAR_POSITIONAL and if it's the first KEYWORD_ONLY
                    if not added_var_positional_marker:
                         is_first_kwonly = all(p.kind != parameter_kinds.KEYWORD_ONLY for p in list(sig.parameters.values())[:i])
                         if is_first_kwonly:
                             param_parts.append('*')

                # 2. Add Annotation
                if param.annotation is not inspect.Parameter.empty:
                    try:
                        # Try common attributes for type names first
                        annot_repr = getattr(param.annotation, '__name__', None) # For simple types/classes
                        if annot_repr is None:
                            annot_repr = getattr(param.annotation, '_name', None) # For typing._GenericAlias like List, Union
                        if annot_repr is None:
                             # Fallback for complex reprs or other types
                             annot_repr = repr(param.annotation).replace('typing.','') 
                        part += f": {annot_repr}"
                    except Exception:
                         part += ": ?" # Fallback if repr/name fails

                # 3. Add Default Value
                if param.default is not inspect.Parameter.empty:
                    part += f" = {repr(param.default)}"
                    
                param_parts.append(part)

                # 4. Handle Positional-Only Separator ('/')
                if param.kind == parameter_kinds.POSITIONAL_ONLY:
                    # Check if this is the *last* positional-only parameter
                    is_last_posonly = all(p.kind != parameter_kinds.POSITIONAL_ONLY for p in list(sig.parameters.values())[i+1:])
                    if is_last_posonly:
                        param_parts.append('/')


            signature_str = f"({', '.join(param_parts)})"

            # 5. Add Return Annotation
            if sig.return_annotation is not inspect.Signature.empty:
                 try:
                    ret_annot_repr = getattr(sig.return_annotation, '__name__', None)
                    if ret_annot_repr is None:
                         ret_annot_repr = getattr(sig.return_annotation, '_name', None)
                    if ret_annot_repr is None:
                         ret_annot_repr = repr(sig.return_annotation).replace('typing.','')
                    signature_str += f" -> {ret_annot_repr}"
                 except Exception:
                    signature_str += " -> ?"

            details["signature"] = signature_str

        except ValueError:
            # Handles built-ins or other non-introspectable callables
            details["signature"] = "(Signature inspection not supported)"
        except TypeError: # Handle cases like built-in methods or slots
            details["signature"] = "(Signature inspection not applicable)"
        except Exception as e:
            # Add more specific logging for unexpected errors during signature inspection
            _logger.warning("Could not get signature for %s (%s): %s", name, type(method_obj), e, exc_info=True)
            details["signature"] = f"(Error inspecting signature: {e})"
            
        # c/d) Determine Type and Decorators (Odoo specific checks)
        decorators_list = []
        method_api = getattr(method_obj, '_api', None)

        # Check specific Odoo API types first
        if method_api == 'model':
            details["method_type"] = "model"
            decorators_list.append("@api.model")
        elif method_api == 'model_create': # Handle both create signatures
            details["method_type"] = "model_create"
            decorators_list.append("@api.model_create_multi or @api.model_create_single")

        # Check standard Python types if not an Odoo API type
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

        # Add other known Odoo decorators by checking their specific attributes
        if hasattr(method_obj, "_depends"):
            try:
                # Arguments are stored directly in _depends
                deps = getattr(method_obj, "_depends", "...")
                # Ensure deps are formatted correctly for display (might be tuple)
                deps_repr = repr(deps) if isinstance(deps, tuple) else str(deps)
                decorators_list.append(f"@api.depends({deps_repr})")
            except Exception as e:
                 _logger.warning(f"Error getting @api.depends args for {name}: {e}")
                 decorators_list.append("@api.depends(...)")

        if hasattr(method_obj, "_returns"):
            try:
                # Model name is the first element of the _returns tuple
                model_name = getattr(method_obj, "_returns", (None,))[0]
                if model_name:
                    decorators_list.append(f"@api.returns('{model_name}')")
            except Exception as e:
                 _logger.warning(f"Error getting @api.returns model for {name}: {e}")
                 decorators_list.append("@api.returns(...)")

        if hasattr(method_obj, "_constrains"):
             try:
                # Arguments are stored directly in _constrains
                cons = getattr(method_obj, "_constrains", "...")
                cons_repr = repr(cons) if isinstance(cons, tuple) else str(cons)
                decorators_list.append(f"@api.constrains({cons_repr})")
             except Exception as e:
                 _logger.warning(f"Error getting @api.constrains args for {name}: {e}")
                 decorators_list.append("@api.constrains(...)")

        if hasattr(method_obj, "_onchange"):
             try:
                # Arguments are stored directly in _onchange
                onch = getattr(method_obj, "_onchange", "...")
                onch_repr = repr(onch) if isinstance(onch, tuple) else str(onch)
                decorators_list.append(f"@api.onchange({onch_repr})")
             except Exception as e:
                 _logger.warning(f"Error getting @api.onchange args for {name}: {e}")
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
