import json
import logging
from typing import Any, List, Optional, Dict, Tuple

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class LLMToolModelMethodExecutor(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self) -> List[Tuple[str, str]]:
        implementations = super()._get_available_implementations()
        return implementations + [
            ("odoo_model_method_executor", "Odoo Model Method Executor"),
        ]

    def odoo_model_method_executor_get_pydantic_model(self):
        """Returns the Pydantic model for the method executor tool parameters."""

        class MethodExecutorParams(BaseModel):
            """
            **HIGH RISK TOOL:** Executes a specified method on an Odoo model or specific records.
            Can modify data, trigger actions, or cause errors if used improperly.
            Requires explicit user confirmation.
            """

            model_config = ConfigDict(
                title=self.name or "odoo_model_method_executor",
            )
            model: str = Field(
                ...,
                description="The technical Odoo model name (e.g., res.partner)",
            )
            method: str = Field(
                ...,
                description="The name of the method to execute on the model or records.",
            )
            record_ids: Optional[List[int]] = Field(
                None,
                description="Optional list of database IDs of the records to execute the method on. If null/empty, the method is called on the model itself (for static/model methods, search, create, etc.).",
            )
            args: Optional[List[Any]] = Field(
                default_factory=list,
                description="Positional arguments to pass to the method.",
            )
            kwargs: Optional[Dict[str, Any]] = Field(
                default_factory=dict,
                description="Keyword arguments to pass to the method.",
            )
            allow_private: bool = Field(
                False,
                description="Set to true to explicitly allow calling methods starting with an underscore ('_'). Use with extreme caution.",
            )

        return MethodExecutorParams

    def odoo_model_method_executor_execute(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes the specified method on the model or records."""
        _logger.info(
            f"Executing Odoo Model Method Executor with parameters: {parameters}"
        )

        model_name = parameters.get("model")
        method_name = parameters.get("method")
        record_ids = parameters.get("record_ids")
        args = parameters.get("args", [])
        kwargs = parameters.get("kwargs", {})
        allow_private = parameters.get("allow_private", False)

        if not model_name or not method_name:
            return {"error": "Model name and method name are required"}

        if model_name not in self.env:
            return {"error": f"Model '{model_name}' does not exist in the environment."}

        if method_name.startswith("_") and not allow_private:
            return {
                "error": f"Execution of private method '{method_name}' is not allowed by default. Set 'allow_private' to true to override."
            }

        try:
            # Get the model
            model_obj = self.env[model_name]

            # Determine the target object (model or recordset)
            if record_ids:
                target = model_obj.browse(record_ids)
                if not target.exists() and len(record_ids) > 0:
                    return {
                        "warning": f"Provided Record IDs {record_ids} do not exist for model {model_name}. Method not executed."
                    }
                elif not target.exists():  # record_ids was empty list
                    target = model_obj  # Fallback to model if empty list provided
            else:
                target = model_obj

            # Get the method function
            method_func = getattr(target, method_name)

            # Execute the method
            _logger.info(
                f"Attempting to call {model_name}.{method_name} on {target} with args: {args}, kwargs: {kwargs}"
            )
            result = method_func(*args, **kwargs)
            _logger.info(f"Method {model_name}.{method_name} executed successfully.")

            # Attempt to serialize the result
            serialized_result = self._serialize_result(result)

            return {
                "result": serialized_result,
                "message": f"Method '{method_name}' executed successfully.",
            }

        except AttributeError:
            _logger.warning(
                f"Method '{method_name}' not found on model '{model_name}' or target '{target}'."
            )
            return {
                "error": f"Method '{method_name}' not found on model '{model_name}'"
            }
        except (TypeError, ValidationError) as e:
            _logger.warning(
                f"Type error executing {method_name} on {model_name}: {e}",
                exc_info=True,
            )
            return {
                "error": f"Incorrect arguments provided for method '{method_name}': {str(e)}"
            }
        except (UserError, AccessError) as e:
            _logger.warning(
                f"Odoo User/Access Error executing {method_name} on {model_name}: {e}",
                exc_info=False,
            )  # Avoid stack trace for expected errors
            return {"error": f"Odoo execution error: {str(e)}"}
        except Exception as e:
            _logger.exception(
                f"Unexpected error executing {method_name} on {model_name}: {str(e)}"
            )
            return {"error": f"An unexpected error occurred: {str(e)}"}

    def _serialize_result(self, result: Any) -> Any:
        """Attempts to serialize the result for JSON compatibility."""
        if isinstance(result, models.BaseModel):
            # If it's a recordset, return a list of IDs or maybe name_get?
            # Returning IDs is safer and more generally useful for the LLM.
            return {"recordset_model": result._name, "record_ids": result.ids}
        try:
            # Try standard JSON serialization
            # This won't work for complex types like datetime, recordsets etc.
            # We might need a more robust serializer or just return repr()
            json.dumps(result)  # Test if serializable
            return result
        except (TypeError, OverflowError):
            _logger.warning(
                f"Result of type {type(result)} is not directly JSON serializable. Returning string representation."
            )
            return repr(result)  # Fallback to string representation
