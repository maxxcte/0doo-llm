import inspect
import logging
from typing import Any, List, Optional, Dict, Tuple

from odoo import _, api, models
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

    def odoo_model_method_inspector_execute(
        self,
        model: str,
        method_name_filter: Optional[str] = None,
        method_type_filter: Optional[List[str]] = None,
        decorator_filter: Optional[List[str]] = None,
        docstring_filter: Optional[str] = None,
        include_private: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Execute the detailed Odoo Model Method Inspector tool.

        Retrieves detailed information about methods of a specific Odoo model, with filtering options.

        Parameters:
            model: The technical Odoo model name (e.g., res.partner) to inspect.
            method_name_filter: Optional filter for methods where the name contains this string (case-insensitive).
            method_type_filter: Optional filter for methods by type. Allowed values: 'instance', 'static', 'class', 'model', 'model_create', 'function'.
            decorator_filter: Optional filter for methods by decorator. Example values: '@api.model', '@api.depends', '@staticmethod'.
            docstring_filter: Optional filter for methods where the docstring contains this string (case-insensitive).
            include_private: Set to true to include methods starting with an underscore ('_'). Defaults to False.
            limit: Maximum number of methods to return (must be >= 1). Defaults to 20.
            offset: Number of methods to skip before returning results (must be >= 0). Defaults to 0.
        """

        if not model:
            raise UserError("Model name is required")

        if model not in self.env:
            raise UserError(f"Model '{model}' does not exist in the environment.")

        actual_limit = limit if limit >= 1 else 20
        actual_offset = offset if offset >= 0 else 0

        total_found, method_details = self._perform_method_inspection(
            model,
            method_name_filter,
            method_type_filter,
            decorator_filter,
            docstring_filter,
            include_private,
            actual_limit,
            actual_offset,
        )
        return {
            "total_found": total_found,
            "limit": actual_limit,
            "offset": actual_offset,
            "returned_count": len(method_details),
            "methods": method_details,
            "message": f"Method inspection complete for {model}. Found {total_found} methods matching criteria. Returning {len(method_details)} methods (limit={actual_limit}, offset={actual_offset}).",
        }

    def _perform_method_inspection(
        self,
        model_name: str,
        name_filter: Optional[str],
        type_filter: Optional[List[str]],
        decorator_filter: Optional[List[str]],
        docstring_filter: Optional[str],
        include_private: bool,
        limit: int,
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

        for name, member in reversed(members):
            if name in processed_names:
                continue

            is_private_method = name.startswith("_")
            if is_private_method and not include_private:
                continue

            if name_filter and name_filter.lower() not in name.lower():
                continue

            details = self._extract_method_details_for_tool(model_cls, member, name)
            if not details:
                continue

            if type_filter and details.get("method_type") not in type_filter:
                continue

            if decorator_filter:
                found_decorator = False
                current_decorators = details.get("decorators", [])
                for dec_filter in decorator_filter:
                    if any(
                        dec_filter in actual_dec for actual_dec in current_decorators
                    ):
                        found_decorator = True
                        break
                if not found_decorator:
                    continue

            if (
                docstring_filter
                and docstring_filter.lower() not in details.get("docstring", "").lower()
            ):
                continue

            method_details_list.append(details)
            processed_names.add(name)

        method_details_list.sort(key=lambda x: x["name"])
        total_found = len(method_details_list)
        start = offset
        end = offset + limit
        sliced_results = method_details_list[start:end]

        return total_found, sliced_results

    def _extract_method_details_for_tool(
        self, model_cls, method_obj, name
    ) -> Optional[Dict[str, Any]]:
        details = {
            "name": name,
            "docstring": "",
            "signature": "(Could not determine signature)",
            "method_type": "unknown",
            "decorators": [],
        }

        try:
            doc = inspect.getdoc(method_obj)
            details["docstring"] = doc.strip() if doc else "(No docstring)"
        except Exception as e:
            _logger.debug("Could not get docstring for %s: %s", name, e)
            details["docstring"] = f"(Error getting docstring: {e})"

        try:
            sig = inspect.signature(method_obj)
            signature_str = f"{name}{sig}"
            details["signature"] = signature_str
        except ValueError:
            details["signature"] = "(Signature inspection not supported)"
        except TypeError:
            details["signature"] = "(Signature inspection not applicable)"
        except Exception as e:
            _logger.warning(
                "Could not get signature for %s (%s): %s",
                name,
                type(method_obj),
                e,
                exc_info=False,
            )
            details["signature"] = f"(Error inspecting signature: {e})"

        decorators_list = []
        method_api = getattr(method_obj, "_api", None)

        try:
            static_attr = inspect.getattr_static(model_cls, name)
            is_staticmethod_static = isinstance(static_attr, staticmethod)
            is_classmethod_static = isinstance(static_attr, classmethod)
        except AttributeError:
            is_staticmethod_static = False
            is_classmethod_static = False

        if method_api == "model":
            details["method_type"] = "model"
            decorators_list.append("@api.model")
        elif method_api == "model_create":
            details["method_type"] = "model_create"
            decorators_list.append("@api.model_create_multi/_single")
        elif is_staticmethod_static:
            details["method_type"] = "static"
            decorators_list.append("@staticmethod")
        elif is_classmethod_static:
            details["method_type"] = "class"
            decorators_list.append("@classmethod")
        elif isinstance(method_obj, staticmethod):
            details["method_type"] = "static"
            decorators_list.append("@staticmethod")
        elif isinstance(method_obj, classmethod):
            details["method_type"] = "class"
            decorators_list.append("@classmethod")
        else:
            if hasattr(method_obj, "__get__"):
                details["method_type"] = "instance"
            elif inspect.isfunction(method_obj):
                details["method_type"] = "function"

        if hasattr(method_obj, "_depends"):
            depends_info = getattr(method_obj, "_depends", {})
            if isinstance(depends_info, dict):
                deps_str = ", ".join(f"'{f}'" for f in depends_info.keys())
            else:
                deps_str = repr(depends_info)
            decorators_list.append(f"@api.depends({deps_str})")
        if hasattr(method_obj, "_constrains"):
            decorators_list.append("@api.constrains(...)")
        if hasattr(method_obj, "_onchange"):
            decorators_list.append("@api.onchange(...)")
        if getattr(method_obj, "deprecated", False):
            decorators_list.append("@api.deprecated")
        details["decorators"] = decorators_list
        return details
