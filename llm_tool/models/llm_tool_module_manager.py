import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from odoo import _, api, exceptions, models
from odoo.tools import config

_logger = logging.getLogger(__name__)


class LLMToolModuleManager(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        # Add check to only enable this tool if not in 'test mode without demo'
        # as module operations might be restricted or undesired in that context.
        # You might refine this check based on your specific deployment needs.
        if config.get("test_enable") and not config.get("demo"):
            return implementations
        return implementations + [("odoo_module_manager", "Odoo Module Manager")]

    def odoo_module_manager_get_pydantic_model(self):
        class ModuleManagerParams(BaseModel):
            """
            **HIGH RISK TOOL:** This tool manages Odoo modules (installs or upgrades).
            It requires Administrator privileges and can cause significant system changes.
            **IMPORTANT:** Before calling this tool, you MUST:
            1. Clearly state which module you intend to install or upgrade.
            2. Explain the reason for this operation.
            3. Explicitly ask the user for confirmation to proceed.
            Only call this tool if the user explicitly confirms.
            """

            model_config = ConfigDict(
                title=self.name or "odoo_module_manager",
            )
            module_name: str = Field(
                ..., description="Technical name of the Odoo module."
            )
            operation: Literal["install", "upgrade"] = Field(
                ..., description="Action to perform: 'install' or 'upgrade'."
            )

        return ModuleManagerParams

    def odoo_module_manager_execute(self, parameters):
        """Execute the Odoo Module Manager tool"""
        _logger.info(f"Executing Odoo Module Manager with parameters: {parameters}")

        # 1. Security Check: Ensure user has System Administrator rights
        if not self.env.user.has_group("base.group_system"):
            _logger.warning(
                "User %s (ID: %s) attempted to use Odoo Module Manager without admin rights.",
                self.env.user.name,
                self.env.user.id,
            )
            return {
                "error": _(
                    "Insufficient Permissions: You must be an Odoo System Administrator "
                    "(belong to the 'base.group_system' group) to manage modules."
                )
            }

        module_name = parameters.get("module_name")
        operation = parameters.get("operation")

        # 2. Parameter Validation
        if not module_name or not operation:
            return {
                "error": _(
                    "Missing required parameters: 'module_name' and 'operation' are required."
                )
            }
        if operation not in ["install", "upgrade"]:
            return {"error": _("Invalid 'operation'. Must be 'install' or 'upgrade'.")}

        # 3. Find the Module
        Module = self.env["ir.module.module"]
        module_record = Module.search([("name", "=", module_name)])

        if not module_record:
            return {"error": _("Module '%s' not found.", module_name)}
        if len(module_record) > 1:  # Should not happen with unique name constraint
            _logger.error("Found multiple modules with name '%s'.", module_name)
            return {
                "error": _(
                    "Internal Error: Found multiple modules with name '%s'.",
                    module_name,
                )
            }

        module_record.ensure_one()
        current_state = module_record.state

        # 4. Execute Operation
        try:
            if operation == "install":
                if current_state == "uninstalled":
                    _logger.info("Attempting to install module '%s'.", module_name)
                    module_record.button_immediate_install()
                    # Re-browse to get the updated state
                    module_record.invalidate_recordset()
                    if module_record.state == "installed":
                        return {
                            "success": _(
                                "Module '%s' installed successfully. Refresh the page to see changes.",
                                module_name,
                            )
                        }
                    else:
                        # This might happen if dependencies fail etc. Odoo usually raises, but check state just in case.
                        _logger.error(
                            "Module '%s' state is '%s' after attempted install.",
                            module_name,
                            module_record.state,
                        )
                        return {
                            "error": _(
                                "Installation of module '%s' initiated but final state is '%s'. Check server logs.",
                                module_name,
                                module_record.state,
                            )
                        }
                elif current_state == "installed":
                    return {"info": _("Module '%s' is already installed.", module_name)}
                else:
                    return {
                        "error": _(
                            "Cannot install module '%s'. It is in state '%s'.",
                            module_name,
                            current_state,
                        )
                    }

            elif operation == "upgrade":
                if current_state in ["installed", "to upgrade"]:
                    _logger.info("Attempting to upgrade module '%s'.", module_name)
                    module_record.button_immediate_upgrade()
                    # Re-browse to get the updated state
                    module_record.invalidate_recordset()
                    if module_record.state == "installed":
                        return {
                            "success": _(
                                "Module '%s' upgraded successfully. Refresh the page to see changes.",
                                module_name,
                            )
                        }
                    else:
                        _logger.error(
                            "Module '%s' state is '%s' after attempted upgrade.",
                            module_name,
                            module_record.state,
                        )
                        return {
                            "error": _(
                                "Upgrade of module '%s' initiated but final state is '%s'. Check server logs.",
                                module_name,
                                module_record.state,
                            )
                        }
                elif current_state == "uninstalled":
                    return {
                        "error": _(
                            "Cannot upgrade module '%s'. It needs to be installed first.",
                            module_name,
                        )
                    }
                else:
                    return {
                        "error": _(
                            "Cannot upgrade module '%s'. It is in state '%s'.",
                            module_name,
                            current_state,
                        )
                    }

        except exceptions.UserError as e:
            _logger.error(
                "UserError during module operation '%s' for module '%s': %s",
                operation,
                module_name,
                str(e),
            )
            return {"error": _("Operation failed: %s", str(e))}
        except Exception as e:
            _logger.exception(
                "Unexpected error during module operation '%s' for module '%s': %s",
                operation,
                module_name,
                str(e),
            )
            return {
                "error": _(
                    "An unexpected error occurred: %s. Check server logs.", str(e)
                )
            }
