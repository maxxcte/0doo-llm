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

        _logger.info(f"Inspecting model: {model_technical_name}")

        model_obj = self.env[model_technical_name]
        model_cls = model_obj.__class__ # Get the actual class object
        members = inspect.getmembers(model_cls, callable) # Inspect the class

        line_vals_list = []
        processed_names = set() # Track names to avoid duplicates from inheritance

        # Use reversed to prioritize methods from the current class over inherited ones
        for name, member in reversed(members):
            if name.startswith('_') and not self.include_private:
                continue
            if name in processed_names:
                continue
            
            # Skip inherited members that are identical to the parent's version
            # This helps clean up noise from models like mail.thread
            # Check if the attribute exists directly on this class's dict
            # If it does, it's either defined here or specifically overridden.
            # If it doesn't, it's purely inherited. We might still want it, 
            # but this check helps if we want to primarily see overrides/new methods.
            # Let's keep purely inherited for now, but refine later if needed.
            # is_directly_defined = name in model_cls.__dict__
            # parent_member = getattr(super(model_cls, model_cls), name, None)
            # if not is_directly_defined and member == parent_member:
            #      _logger.debug(f"Skipping identical inherited member: {name}")
            #      continue
            
            details = self._extract_method_details(model_cls, member, name) # Pass model_cls
            if details:
                line_vals_list.append(details)
                processed_names.add(name)

        # Create lines if any details were extracted
        if line_vals_list:
            self.method_lines = [(0, 0, vals) for vals in line_vals_list]

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # Pass the class object (model_cls) as the first argument now
    def _extract_method_details(self, model_cls, method_obj, name):
        details = {
            "wizard_id": self.id, # Link back to the wizard
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
            # Check if method_obj itself is callable, or if it wraps a callable
            target_callable = method_obj
            # Handle staticmethod/classmethod wrappers
            if isinstance(method_obj, (staticmethod, classmethod)):
                target_callable = getattr(method_obj, '__func__', method_obj)
            
            # Handle potential Odoo decorators wrapping the function
            while hasattr(target_callable, '__wrapped__'):
                target_callable = target_callable.__wrapped__

            # Ensure we have something inspectable
            if not callable(target_callable):
                 raise TypeError("Object is not callable after unwrapping")

            sig = inspect.signature(target_callable)
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

        # DEBUG: Log the type of the method object before classification
        _logger.info(f"Inspecting method: {name}, Type: {type(method_obj)}")
        # Add specific check for the problematic method for easier spotting
        if name == 'serialize_model_data':
            _logger.info(f"DEBUG CHECK for '{name}': Type is {type(method_obj)}, Is staticmethod? {isinstance(method_obj, staticmethod)}")

        # c/d) Determine Type and Decorators (Odoo specific checks)
        decorators_list = []
        method_api = getattr(method_obj, '_api', None)

        # --- Reliable check using inspect.getattr_static ---
        try:
            # Get the attribute without triggering descriptor protocol
            static_attr = inspect.getattr_static(model_cls, name)
            is_staticmethod_static = isinstance(static_attr, staticmethod)
            is_classmethod_static = isinstance(static_attr, classmethod)
        except AttributeError:
            # Should not happen if name came from getmembers, but handle defensively
            is_staticmethod_static = False
            is_classmethod_static = False
        # --- End reliable check ---

        # Check specific Odoo API types first
        if method_api == 'model':
            details["method_type"] = "model"
            decorators_list.append("@api.model")
        elif method_api == 'model_create': # Handle both create signatures
            details["method_type"] = "model_create"
            decorators_list.append("@api.model_create_multi or @api.model_create_single")
        
        # Now use the reliable getattr_static check
        elif is_staticmethod_static:
            details["method_type"] = "static"
            decorators_list.append("@staticmethod")
        elif is_classmethod_static:
            details["method_type"] = "class"
            decorators_list.append("@classmethod")

        # Fallback to previous logic if not detected via dict (less likely needed now)
        elif isinstance(method_obj, staticmethod):
            _logger.warning(f"Detected staticmethod '{name}' via isinstance fallback, not getattr_static.")
            details["method_type"] = "static"
            decorators_list.append("@staticmethod")
        elif isinstance(method_obj, classmethod):
            _logger.warning(f"Detected classmethod '{name}' via isinstance fallback, not getattr_static.")
            details["method_type"] = "class"
            decorators_list.append("@classmethod")
        else:
            # Assume instance method if not otherwise identified
            # Check if it's bound to the class via descriptor protocol typical for instance methods
            # Needs refinement: A plain function in class is not necessarily instance method
            if hasattr(method_obj, '__get__') and not isinstance(method_obj, (staticmethod, classmethod)):
                 # Check if it's actually a bound method descriptor or just a function
                 # If it's just a function, __get__ exists but it's not a typical 'instance' method yet
                 # For now, let's keep classifying it as instance if it has __get__
                 details["method_type"] = "instance" 
            elif inspect.isfunction(method_obj):
                details["method_type"] = "function"
                # Optionally add a note if it's a function found directly on the class
                # decorators_list.append("(class-level function)") 

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
