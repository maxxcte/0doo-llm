import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class LLMKnowledgeChunker(models.Model):
    _inherit = "llm.resource"

    state = fields.Selection(
        selection_add=[
            ("chunked", "Chunked"),
            ("ready", "Ready"),
        ],
    )

    collection_ids = fields.Many2many(
        "llm.knowledge.collection",
        relation="llm_knowledge_resource_collection_rel",
        column1="resource_id",
        column2="collection_id",
        string="Collections",
    )

    def process_resource(self):
        """
        Override the process_resource method to include chunking and embedding steps
        """
        # Call the original process_resource to handle retrieval and parsing
        super().process_resource()

        # Process chunking and embedding
        inconsistent_docs = self.filtered(
            lambda d: d.state in ["chunked", "ready"] and not d.chunk_ids
        )

        if inconsistent_docs:
            inconsistent_docs.write({"state": "parsed"})

        # Process chunks for parsed documents
        parsed_docs = self.filtered(lambda d: d.state == "parsed")
        if parsed_docs:
            parsed_docs.chunk()

        # Embed chunked documents
        chunked_docs = self.filtered(lambda d: d.state == "chunked")
        if chunked_docs:
            chunked_docs.embed()

        return True

    def action_embed(self):
        """Action handler for embedding document chunks"""
        result = self.embed()
        # Return appropriate notification
        if result:
            self._post_styled_message(
                _("Document embedding process completed successfully."),
                "success",
            )
            return True
        else:
            message = _("Document embedding process did not complete properly, check logs on resources."),
                
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Embedding"),
                    "message": message,
                    "type": "warning",
                    "sticky": False,
                },
            }

    def action_reindex(self):
        """Reindex a single resource's chunks"""
        self.ensure_one()

        # Get all collections this resource belongs to
        collections = self.collection_ids
        if not collections:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Reindexing"),
                    "message": _("Resource does not belong to any collections."),
                    "type": "warning",
                },
            }

        # Get all chunks for this resource
        chunks = self.chunk_ids
        if not chunks:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Reindexing"),
                    "message": _("No chunks found for this resource."),
                    "type": "warning",
                },
            }

        # Set resource back to chunked state to trigger re-embedding
        self.write({"state": "chunked"})

        # Delete chunks from each collection's store
        for collection in collections:
            if collection.store_id:
                # Remove chunks from this resource from the store
                try:
                    collection.delete_vectors(ids=chunks.ids)
                except Exception as e:
                    _logger.warning(
                        f"Error removing vectors for chunks from collection {collection.id}: {str(e)}"
                    )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reindexing"),
                "message": _(
                    f"Reset resource for re-embedding in {len(collections)} collections."
                ),
                "type": "success",
            },
        }

    def action_mass_reindex(self):
        """Reindex multiple resources at once"""
        collections = self.env["llm.knowledge.collection"]
        for resource in self:
            # Add to collections set
            collections |= resource.collection_ids

        # Reindex each affected collection
        for collection in collections:
            collection.reindex_collection()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reindexing"),
                "message": _(
                    f"Reindexing request submitted for {len(collections)} collections."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def embed(self):
        """
        Embed resource chunks in collections by calling the collection's embed_resources method.
        Called after chunking to create vector representations.

        Returns:
            bool: True if any resources were successfully embedded, False otherwise
        """
        # Filter to only get resources in chunked state
        chunked_docs = self.filtered(lambda d: d.state == "chunked")

        if not chunked_docs:
            self._post_styled_message(
                _("No resources in 'chunked' state to embed."),
                "warning",
            )
            return False

        # Get all collections for these resources
        collections = self.env["llm.knowledge.collection"]
        for doc in chunked_docs:
            collections |= doc.collection_ids

        # If no collections, resources can't be embedded
        if not collections:
            self._post_styled_message(
                _("No collections found for the selected resources."),
                "warning",
            )
            return False

        # Track if any resources were embedded
        any_embedded = False

        # Let each collection handle the embedding
        for collection in collections:
            result = collection.embed_resources(specific_resource_ids=chunked_docs.ids)
            # Check if result is not None before trying to access .get()
            if (
                result
                and result.get("success")
                and result.get("processed_resources", 0) > 0
            ):
                any_embedded = True

        if not any_embedded:
            self._post_styled_message(
                _("No resources could be embedded. Check that resources have correct collections and collections have valid embedding models and stores."),
                "warning",
            )
        # Return True only if resources were actually embedded
        return any_embedded

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle collection_ids and apply chunking settings"""
        # Create the resources first
        resources = super().create(vals_list)
        
        # Process each resource that has collections
        for resource in resources:
            if resource.collection_ids and resource.state not in ['chunked', 'ready']:
                # Get the first collection's settings
                collection = resource.collection_ids[0]
                # Update the resource with the collection's settings
                update_vals = {
                    "target_chunk_size": collection.default_chunk_size,
                    "target_chunk_overlap": collection.default_chunk_overlap,
                    "chunker": collection.default_chunker,
                    "parser": collection.default_parser,
                }
                resource.write(update_vals)
        
        return resources

    @api.model
    def action_mass_process_resources(self):
        """
        Server action handler for mass processing resources.
        This will be triggered from the server action in the UI.
        """
        active_ids = self.env.context.get("active_ids", [])
        if not active_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Resources Selected"),
                    "message": _("Please select resources to process."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        resources = self.browse(active_ids)
        # Process all selected resources
        result = resources.process_resource()

        if result:
            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }

        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Processing Failed"),
                    "message": _("Mass processing resources failed"),
                    "sticky": False,
                    "type": "danger",
                },
            }

    def _reset_state_if_needed(self):
        """Reset resource state to 'chunked' if it's in 'ready' state and not in any collection."""
        self.ensure_one()
        if self.state == 'ready' and not self.collection_ids:
            self.write({'state': 'chunked'})
            _logger.info(f"Reset resource {self.id} to 'chunked' state after removal from all collections")
            self._post_styled_message(
                _("Reset to 'chunked' state after removal from all collections"),
                "info",
            )
        return True

    def _handle_collection_ids_change(self, old_collections_by_resource):
        """Handle changes to collection_ids field.
        
        Args:
            old_collections_by_resource: Dictionary mapping resource IDs to their previous collection IDs
        """
        for resource in self:
            old_collection_ids = old_collections_by_resource.get(resource.id, [])
            current_collection_ids = resource.collection_ids.ids
            
            # Find collections that the resource was removed from
            removed_collection_ids = [cid for cid in old_collection_ids if cid not in current_collection_ids]
            
            # Clean up vectors in those collections' stores
            if removed_collection_ids:
                collections = self.env['llm.knowledge.collection'].browse(removed_collection_ids)
                for collection in collections:
                    # Use the collection's method to handle resource removal
                    collection._handle_removed_resources([resource.id])
        
        return True

    def write(self, vals):
        """Override write to handle collection_ids changes and cleanup vectors if needed"""
        # Track collections before the write
        resources_collections = {}
        if 'collection_ids' in vals:
            for resource in self:
                resources_collections[resource.id] = resource.collection_ids.ids
        
        # Perform the write operation
        result = super().write(vals)
        
        # Handle collection changes
        if 'collection_ids' in vals:
            self._handle_collection_ids_change(resources_collections)
        
        return result
