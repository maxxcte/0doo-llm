from odoo import api, models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def rag_retrieve(self, llm_document):
        """
        Implementation of rag_retrieve for ir.attachment model.
        This method updates the existing attachment to link it directly
        to the LLM document.

        :param llm_document: The llm.document record being processed
        """
        self.ensure_one()

        # Update the existing attachment to link it to the llm.document
        self.write({
            'res_model': 'llm.document',  # Link to llm.document model
            'res_id': llm_document.id,    # Link to this specific document
        })

        # Optionally post a message in the chatter for traceability
        llm_document.message_post(
            body=f"Retrieved attachment: {self.name}",
        )
