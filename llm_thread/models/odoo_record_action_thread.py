import threading
import logging

from odoo import api, registry, SUPERUSER_ID

_logger = logging.getLogger(__name__)


class OdooRecordActionThread(threading.Thread):
    """Generic background thread to run a method on a specific Odoo record."""

    def __init__(self, dbname, uid, context, model_name, record_id, method_name, method_args=None, method_kwargs=None):
        super().__init__(name=f"odoo_action_{model_name}_{record_id}_{method_name}", daemon=True)
        self.dbname = dbname
        self.uid = uid
        self.context = context
        self.model_name = model_name
        self.record_id = record_id
        self.method_name = method_name
        self.method_args = method_args if method_args is not None else ()
        self.method_kwargs = method_kwargs if method_kwargs is not None else {}

    def run(self):
        """Target function for the background thread."""
        try:
            with api.Environment.manage():
                reg = registry(self.dbname)
                with reg.cursor() as new_cr:
                    env = api.Environment(new_cr, self.uid, self.context)
                    record = env[self.model_name].browse(self.record_id)

                    if record.exists():
                        method_to_call = getattr(record, self.method_name, None)
                        if method_to_call and callable(method_to_call):
                            method_to_call(*self.method_args, **self.method_kwargs)
                            _logger.info(
                                f"Background thread {self.name}: Finished {self.method_name} on {self.model_name} {self.record_id}"
                            )
                        else:
                            _logger.error(
                                f"Background thread {self.name}: Method '{self.method_name}' not found or not callable on {self.model_name} {self.record_id}"
                            )
                    else:
                        _logger.error(
                             f"Background thread {self.name}: Could not find {self.model_name} {self.record_id} in db {self.dbname}"
                        )

        except Exception as e:
            _logger.error(f"Error in background thread {self.name} (DB: {self.dbname}): {e}")