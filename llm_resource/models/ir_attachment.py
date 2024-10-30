from odoo import models


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def llm_get_fields(self, _):
        self.ensure_one()
        is_markdown = self.file_name.lower().endswith(".md") and self.mimetype == "stream/octet-stream"
        return [{
            "field_name": "datas",
            "mimetype": "text/markdown" if is_markdown else self.mimetype,
            "rawcontent": self.raw,
        }]
