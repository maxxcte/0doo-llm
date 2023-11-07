from odoo import api, models


class DocumentPage(models.Model):
    """Extend document.page to add integration with LLM RAG module."""

    _inherit = "document.page"

    def rag_parse(self, llm_document):
        """
        Parse document.page content for RAG.
        This method is called by the LLM RAG module during document processing.

        :param llm_document: The llm.document record being processed
        :return: Boolean indicating success
        """
        self.ensure_one()

        # Start with the page title as heading
        content_parts = [f"# {self.name}"]

        # Get page metadata
        metadata = []
        if self.content_uid:
            metadata.append(f"**Last Contributor:** {self.content_uid.name}")
        if self.content_date:
            metadata.append(f"**Last Updated:** {self.content_date}")
        if self.parent_id:
            metadata.append(f"**Category:** {self.parent_id.name}")

        # Add metadata section if we have any
        if metadata:
            content_parts.append("\n## Metadata\n")
            content_parts.append("\n".join(metadata))

        # Add main content
        content_parts.append("\n## Content\n")

        # The content is already in HTML, but we need to convert it to markdown
        # The simplest approach is to use the content directly if it's already parsed
        # For document.page, the content field is already HTML which works well with markdown
        content_parts.append(self.content)

        # If there are child pages, include their titles as references
        if self.child_ids:
            content_parts.append("\n## Related Pages\n")
            for child in self.child_ids:
                content_parts.append(f"- [{child.name}]({child.backend_url})")

        # Set the content in the llm.document
        llm_document.content = "\n\n".join(content_parts)

        # Post success message
        llm_document._post_message(
            f"Successfully parsed document page: {self.name}",
            message_type="success",
        )

        return True
