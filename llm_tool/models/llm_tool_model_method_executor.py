import json
import logging
from typing import Any, Optional

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMToolModelMethodExecutor(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self) -> list[tuple[str, str]]:
        implementations = super()._get_available_implementations()
        return implementations + [
            ("odoo_model_method_executor", "Odoo Model Method Executor"),
        ]

    def odoo_model_method_executor_execute(
        self,
        model: str,
        method: str,
        record_ids: Optional[list[int]] = None,
        args: Optional[list[Any]] = None,
        kwargs: Optional[dict[str, Any]] = None,
        allow_private: bool = False,
    ) -> dict[str, Any]:
        """Executes the specified method on the model or records.

        Parameters:
            model: The technical Odoo model name (e.g., res.partner).
            method: The name of the method to execute on the model or records.
            record_ids: Optional list of database IDs. If provided, the method is called on this recordset; otherwise, it's called on the model.
            args: Optional list of positional arguments to pass to the method.
            kwargs: Optional dictionary of keyword arguments to pass to the method.
            allow_private: Set to true to allow calling private methods (those starting with '_'). Defaults to False.
        """
        actual_args = args if args is not None else []
        actual_kwargs = kwargs if kwargs is not None else {}

        if not model or not method:
            return {"error": "Model name and method name are required"}

        if model not in self.env:
            raise UserError(f"Model '{model}' does not exist in the environment.")

        if method.startswith("_") and not allow_private:
            raise UserError(
                f"Execution of private method '{method}' is not allowed by default. "
                "Set 'allow_private' to true to override."
            )

        model_obj = self.env[model]
        target = model_obj

        if record_ids:
            target = model_obj.browse(record_ids)
            if not target.exists():
                existing_ids = model_obj.search([("id", "in", record_ids)]).ids
                if not existing_ids:
                    return {
                        "error": f"None of the provided Record IDs {record_ids} exist for model {model}."
                    }

        if not hasattr(target, method):
            target_type = "records" if record_ids else "model"
            raise AttributeError(
                f"Method '{method}' not found on the target {target_type} ('{target}')."
            )

        method_func = getattr(target, method)

        result = method_func(*actual_args, **actual_kwargs)

        serialized_result = self._serialize_result(result)
        return {
            "result": serialized_result,
            "message": f"Method '{method}' executed successfully.",
        }

    def _serialize_result(self, result: Any) -> Any:
        if isinstance(result, models.BaseModel):
            return {"recordset_model": result._name, "record_ids": result.ids}
        try:
            json.dumps(result)
            return result
        except (TypeError, OverflowError):
            return repr(result)
