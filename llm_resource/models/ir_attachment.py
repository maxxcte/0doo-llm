import base64
from odoo import models


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def llm_get_fields(self):
        # TODO optimise to return open file stream instead of entire raw data
        return [("datas", self.mimetype, self.raw)]
