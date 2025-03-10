import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class LLMPromptController(http.Controller):
    """Controller for LLM Prompt API endpoints"""

    @http.route(
        "/api/llm/prompts/list", type="json", auth="user", csrf=False, methods=["POST"]
    )
    def list_prompts(self, provider_id=None, **kwargs):
        """
        List available prompts for a provider

        Args:
            provider_id: ID of the provider (optional, uses default if not provided)

        Returns:
            dict: List of available prompts
        """
        try:
            # Get provider
            if provider_id:
                provider = request.env["llm.provider"].browse(int(provider_id))
                if not provider.exists():
                    return {"error": "Provider not found"}
            else:
                # Get default provider
                provider = request.env["llm.provider"].search(
                    [("active", "=", True)],
                    limit=1,
                )
                if not provider:
                    return {"error": "No active provider found"}

            # Get prompts
            prompts = provider.list_prompts()

            return {"prompts": prompts}

        except Exception as e:
            _logger.exception("Error listing prompts: %s", str(e))
            return {"error": str(e)}

    @http.route(
        "/api/llm/prompts/get", type="json", auth="user", csrf=False, methods=["POST"]
    )
    def get_prompt(self, name, provider_id=None, arguments=None, **kwargs):
        """
        Get a specific prompt with arguments

        Args:
            name: Name of the prompt to get
            provider_id: ID of the provider (optional, uses default if not provided)
            arguments: Dictionary of argument values

        Returns:
            dict: Prompt result with messages
        """
        try:
            # Parse arguments if provided as string
            if arguments and isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    return {"error": "Invalid arguments JSON format"}

            # Get provider
            if provider_id:
                provider = request.env["llm.provider"].browse(int(provider_id))
                if not provider.exists():
                    return {"error": "Provider not found"}
            else:
                # Get default provider
                provider = request.env["llm.provider"].search(
                    [("active", "=", True)],
                    limit=1,
                )
                if not provider:
                    return {"error": "No active provider found"}

            # Get prompt
            try:
                result = provider.get_prompt(name, arguments)
                return result
            except Exception as e:
                return {"error": str(e)}

        except Exception as e:
            _logger.exception("Error getting prompt: %s", str(e))
            return {"error": str(e)}
