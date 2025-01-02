import base64
import logging
from urllib.parse import urlparse

from mistralai import Mistral

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _get_available_services(self):
        services = super()._get_available_services()
        return services + [("mistral", "Mistral AI")]

    def _dispatch(self, method, *args, record=None, **kwargs):
        if not self.service:
            raise UserError(_("Provider service not configured"))
        if self.service == "mistral":
            # Mistral uses OpenAI compatible API for many things
            service_method = f"openai_{method}"
            record = record if record else self
            record_name = record._name
            if not hasattr(record, service_method):
                raise NotImplementedError(
                    _(
                        "Method '%s' (via '%s') not implemented for service '%s' on target '%s'"
                    )
                    % (method, service_method, self.service, record_name)
                )

            return getattr(record, service_method)(*args, **kwargs)
        else:
            return super()._dispatch(method, *args, record=record, **kwargs)
    
    def _openai_parse_model(self, model):
        if self.service == "mistral":
            model_json_dump = model.model_dump()
            capabilities = []
            model_caps = model_json_dump["capabilities"]
            if model_caps["vision"]:
                capabilities.append("multimodal")
            elif model_caps["completion_chat"]:
                capabilities.append("chat")
            elif "ocr" in model.id:
                capabilities.append("ocr")
            elif "embed" in model.id:
                capabilities.append("embedding")
            else:
                capabilities.append("chat")

            model_json_dump.pop("capabilities", None)
            return {
                "name": model.id,
                "details": {
                    "id": model.id,
                    "capabilities": capabilities,
                    **model_json_dump,
                },
            }
        else:
            return super()._openai_parse_model(model)

    def _get_mistral_client(self):
        self.ensure_one()

        return Mistral(
            api_key=self.api_key,
        )

    def process_ocr(self, model_name, data, mimetype, **kwargs):
        self.ensure_one()

        if isinstance(data, bytes):
            # Convert bytes to base64 string
            data = base64.b64encode(data).decode("utf-8")
        elif not isinstance(data, str):
            raise TypeError(
                f"Input 'data' must be a string (URL, bytes or Base64) or bytes. Got: {type(data)}"
            )

        if not mimetype:
            raise ValueError("Mimetype parameter is required.")

        payload = {}
        is_image_type = mimetype.startswith("image/")
        data_is_url = is_url(data)
        data_is_base64 = False  # Check only if not a URL

        if data_is_url:
            _logger.info(f"Processing data as URL: {data} with mimetype: {mimetype}")
            if is_image_type:
                payload = {
                    "type": "image_url",
                    "image_url": data,  # Pass the raw URL
                }
            else:
                payload = {
                    "type": "document_url",
                    "document_url": data,  # Pass the raw URL
                }
        else:
            # If not a URL, check if it's a valid Base64 string
            data_is_base64 = is_base64_string(data)
            if data_is_base64:
                _logger.info(f"Processing data as Base64 string (mimetype: {mimetype})")
                # Construct the data URI
                data_uri = f"data:{mimetype};base64,{data}"

                if is_image_type:
                    payload = {"type": "image_url", "image_url": data_uri}
                else:
                    payload = {"type": "document_url", "document_url": data_uri}
            else:
                # Input string is neither a valid URL nor valid Base64
                raise ValueError(
                    "Input 'data' string is neither a valid URL nor a valid Base64 string."
                )

        # Ensure a payload was actually constructed
        if not payload:
            # This state should theoretically not be reached if the logic above is sound
            raise ValueError("Internal Error: Failed to construct payload.")
        # Call the actual method that interacts with the Mistral API
        return self._process_ocr(model_name, payload, **kwargs)

    def _process_ocr(self, model_name, payload):
        mistral_client = self._get_mistral_client()
        return mistral_client.ocr.process(
            model=model_name, document=payload, include_image_base64=True
        )


def is_base64_string(data_string):
    """
    Checks if the provided string appears to be a valid Base64 encoded string.

    Note: This checks the format (characters, padding, length), but doesn't
    guarantee the decoded data is meaningful.

    Args:
      data_string: The string to check.

    Returns:
      True if the string could be Base64, False otherwise.
    """
    if not isinstance(data_string, str):
        return False
    try:
        string_bytes = data_string.encode("ascii")
        base64.b64decode(string_bytes, validate=True)
        return len(string_bytes) % 4 == 0
    except Exception as e:
        _logger.exception(f"Base64 check failed, error: {str(e)}")
        return False


def is_url(data_string):
    """
    Checks if the provided string is a valid HTTP or HTTPS URL.

    Args:
      data_string: The string to check.

    Returns:
      True if the string is a valid HTTP/HTTPS URL, False otherwise.
    """
    if not isinstance(data_string, str):
        return False
    try:
        result = urlparse(data_string)
        return all([result.scheme in ["http", "https"], result.netloc])
    except Exception as e:
        _logger.exception(f"Url check failed, error: {str(e)}")
        return False
