# -*- coding: utf-8 -*-
import logging
import inspect
from typing import List, Optional, Dict, Any, Tuple

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class LLMToolModelMethodInspector(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self) -> List[Tuple[str, str]]:
        implementations = super()._get_available_implementations()
        return implementations + [
            ("odoo_model_method_inspector", "Odoo Model Method Inspector (Detailed)"),
        ]

    def odoo_model_method_inspector_get_pydantic_model(self):
        """Returns the Pydantic model for the method inspector tool parameters."""
        class MethodInspectorParams(BaseModel):
            """Retrieves detailed information about methods of a specific Odoo model, with filtering options."""

            model_config = ConfigDict(
                title=self.name or "odoo_model_method_inspector",
            )
            model: str = Field(
                ...,
                description="The technical Odoo model name (e.g., res.partner)",
            )
            method_name_filter: Optional[str] = Field(
                None,
                description="Filter methods where the name contains this string (case-insensitive).",
            )
            method_type_filter: Optional[List[str]] = Field(
                None,
                description="Filter methods by type. Allowed values: 'instance', 'static', 'class', 'model', 'model_create', 'function'.",
            )
            decorator_filter: Optional[List[str]] = Field(
                None,
                description="Filter methods by decorator. Example values: '@staticmethod', '@api.model', '@api.depends', '@api.constrains', '@api.onchange'.",
            )
            docstring_filter: Optional[str] = Field(
                None,
                description="Filter methods where the docstring contains this string (case-insensitive).",
            )
            include_private: bool = Field(
                False, description="Include methods starting with an underscore ('_')."
            )
            limit: int = Field(
                20, 
                description="Maximum number of methods to return (must be 1 or greater). Defaults to 20. Set explicitly higher for more results, respecting system limits.",
                ge=1 # Limit must be at least 1 if provided
            )
            offset: int = Field(
                0, 
                description="Number of methods to skip before returning results.",
                ge=0
            )

        return MethodInspectorParams

    def odoo_model_method_inspector_execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the detailed Odoo Model Method Inspector tool"""
        _logger.info(f"Executing Odoo Model Method Inspector with parameters: {parameters}")

        model_name = parameters.get("model")
        if not model_name:
            return {"error": "Model name is required"}

        if model_name not in self.env:
            return {"error": f"Model '{model_name}' does not exist in the environment."}

        try:
            limit = parameters.get("limit") # Can be None
            offset = parameters.get("offset", 0)
            
            total_found, method_details = self._perform_method_inspection(
                model_name,
                parameters.get("method_name_filter"),
                parameters.get("method_type_filter"),
                parameters.get("decorator_filter"),
                parameters.get("docstring_filter"), # Pass the new filter
                parameters.get("include_private", False),
                limit,
                offset,
            )
            return {
                "total_found": total_found,
                "limit": limit,
                "offset": offset,
                "returned_count": len(method_details),
                "methods": method_details,
                "message": f"Method inspection complete for {model_name}. Found {total_found} methods matching criteria. Returning {len(method_details)} methods (limit={limit}, offset={offset})."
            }

        except Exception as e:
            _logger.exception(f"Error executing Odoo Model Method Inspector: {str(e)}")
            return {"error": str(e)}

    # --- Helper Methods (Refactored from Wizard) ---

    def _perform_method_inspection(
        self,
        model_name: str,
        name_filter: Optional[str],
        type_filter: Optional[List[str]],
        decorator_filter: Optional[List[str]],
        docstring_filter: Optional[str], # Add parameter here
        include_private: bool,
        limit: Optional[int],
        offset: int,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Inspects a model, returns total count and a sliced list of method details."""
        try:
            model_obj = self.env[model_name]
            model_cls = model_obj.__class__
        except KeyError:
            raise UserError(_("Model '%s' not found in Odoo environment.") % model_name)

        members = inspect.getmembers(model_cls, callable)
        method_details_list = []
        processed_names = set()

        for name, member in reversed(members): # Prioritize subclass methods
            if name in processed_names:
                continue

            is_private_method = name.startswith('_')
            if is_private_method and not include_private:
                continue

            # Basic name filter (case-insensitive)
            if name_filter and name_filter.lower() not in name.lower():
                continue

            details = self._extract_method_details_for_tool(model_cls, member, name)
            if not details: # Skip if extraction failed somehow
                 continue

            # Type filter
            if type_filter and details.get("method_type") not in type_filter:
                continue

            # Decorator filter (check if any requested decorator is present)
            if decorator_filter:
                found_decorator = False
                current_decorators = details.get("decorators", [])
                for dec_filter in decorator_filter:
                     # Simple check, might need refinement for args like @api.depends('field')
                    if any(dec_filter in actual_dec for actual_dec in current_decorators):
                        found_decorator = True
                        break
                if not found_decorator:
                    continue
            
            # Docstring filter (case-insensitive)
            if docstring_filter and docstring_filter.lower() not in details.get("docstring", "").lower():
                continue

            method_details_list.append(details)
            processed_names.add(name)
            
        # Sort alphabetically for consistent output
        method_details_list.sort(key=lambda x: x['name'])
        
        total_found = len(method_details_list)

        # Apply limit and offset
        start = offset
        end = offset + limit if limit is not None else None
        sliced_results = method_details_list[start:end]

        return total_found, sliced_results

    def _extract_method_details_for_tool(self, model_cls, method_obj, name) -> Optional[Dict[str, Any]]:
        """Extracts details for a single method, adapted for tool output."""
        details = {
            "name": name,
            "docstring": "",
            "signature": "(Could not determine signature)",
            "method_type": "unknown",
            "decorators": [], # List to store decorator strings
        }

        # a) Docstring
        try:
            doc = inspect.getdoc(method_obj)
            details["docstring"] = doc.strip() if doc else "(No docstring)"
        except Exception as e:
            _logger.debug("Could not get docstring for %s: %s", name, e)
            details["docstring"] = f"(Error getting docstring: {e})"

        # b) Signature
        try:
            sig = inspect.signature(method_obj)
            signature_str = f"{name}{sig}"
            details["signature"] = signature_str
        except ValueError: # Handles built-ins etc.
            details["signature"] = "(Signature inspection not supported)"
        except TypeError: # Handle slots, etc.
            details["signature"] = "(Signature inspection not applicable)"
        except Exception as e:
            _logger.warning("Could not get signature for %s (%s): %s", name, type(method_obj), e, exc_info=False)
            details["signature"] = f"(Error inspecting signature: {e})"

        # c/d) Determine Type and Decorators
        decorators_list = []
        method_api = getattr(method_obj, '_api', None)

        try:
            static_attr = inspect.getattr_static(model_cls, name)
            is_staticmethod_static = isinstance(static_attr, staticmethod)
            is_classmethod_static = isinstance(static_attr, classmethod)
        except AttributeError:
            is_staticmethod_static = False
            is_classmethod_static = False

        if method_api == 'model':
            details["method_type"] = "model"
            decorators_list.append("@api.model")
        elif method_api == 'model_create':
            details["method_type"] = "model_create"
            decorators_list.append("@api.model_create_multi/_single")
        elif is_staticmethod_static:
            details["method_type"] = "static"
            decorators_list.append("@staticmethod")
        elif is_classmethod_static:
            details["method_type"] = "class"
            decorators_list.append("@classmethod")
        elif isinstance(method_obj, staticmethod): # Fallback
            details["method_type"] = "static"
            decorators_list.append("@staticmethod")
        elif isinstance(method_obj, classmethod): # Fallback
            details["method_type"] = "class"
            decorators_list.append("@classmethod")
        else:
            # Default assumption
            if hasattr(method_obj, '__get__'):
                 details["method_type"] = "instance" 
            elif inspect.isfunction(method_obj):
                details["method_type"] = "function"

        # Add other known Odoo decorators
        if hasattr(method_obj, "_depends"):
            depends_info = getattr(method_obj, "_depends", {})
            if isinstance(depends_info, dict):
                 # New style @api.depends
                 deps_str = ', '.join(f"'{f}'" for f in depends_info.keys())
            else: 
                 # Old style (less common now)
                 deps_str = repr(depends_info) # Fallback representation
            decorators_list.append(f"@api.depends({deps_str})")
        if hasattr(method_obj, "_constrains"):
            # Similar logic could be added for depends args if needed
            decorators_list.append("@api.constrains(...)") 
        if hasattr(method_obj, "_onchange"):
            decorators_list.append("@api.onchange(...)")
        if getattr(method_obj, "deprecated", False):
             decorators_list.append("@api.deprecated")
        # Add more decorator checks here if needed (e.g., returns, specific RPC types)

        details["decorators"] = decorators_list
        return details
