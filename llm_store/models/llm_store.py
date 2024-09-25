from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LLMStore(models.Model):
    _name = "llm.store"
    _inherit = ["mail.thread"]
    _description = "LLM Vector Store"

    name = fields.Char(required=True, tracking=True)
    service = fields.Selection(
        selection=lambda self: self._selection_service(),
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    
    # Connection parameters
    connection_uri = fields.Char(tracking=True)
    api_key = fields.Char(tracking=True)
    
    # Additional metadata 
    metadata = fields.Json(string="Store Metadata")
    
    def _dispatch(self, method, *args, **kwargs):
        """Dispatch method call to appropriate service implementation"""
        if not self.service:
            raise UserError(_("Vector store service not configured"))

        service_method = f"{self.service}_{method}"
        if not hasattr(self, service_method):
            raise NotImplementedError(
                _("Method %s not implemented for service %s") % (method, self.service)
            )

        return getattr(self, service_method)(*args, **kwargs)

    @api.model
    def _selection_service(self):
        """Get all available services from store implementations"""
        services = []
        for service in self._get_available_services():
            services.append(service)
        return services

    @api.model
    def _get_available_services(self):
        """Hook method for registering vector store services"""
        return []

    # Collection Management
    def create_collection(self, name, dimension=None, metadata=None, **kwargs):
        """Create a new collection with the specified parameters
        
        Args:
            name: Name of the collection
            dimension: Dimension of the vectors (required for some stores)
            metadata: Additional metadata for the collection
            **kwargs: Additional store-specific parameters
            
        Returns:
            Collection info dictionary
        """
        return self._dispatch("create_collection", name, dimension, metadata, **kwargs)

    def delete_collection(self, name, **kwargs):
        """Delete a collection by name
        
        Args:
            name: Name of the collection to delete
            **kwargs: Additional store-specific parameters
            
        Returns:
            Boolean indicating success
        """
        return self._dispatch("delete_collection", name, **kwargs)

    def list_collections(self, **kwargs):
        """List all collections
        
        Args:
            **kwargs: Additional store-specific parameters
            
        Returns:
            List of collection names/info
        """
        return self._dispatch("list_collections", **kwargs)

    def collection_exists(self, name, **kwargs):
        """Check if a collection exists
        
        Args:
            name: Name of the collection to check
            **kwargs: Additional store-specific parameters
            
        Returns:
            Boolean indicating if collection exists
        """
        return self._dispatch("collection_exists", name, **kwargs)

    # Vector Management
    def _insert_vectors(self, collection_id, vectors, metadata=None, ids=None, **kwargs):
        """Insert vectors into a collection
        
        Args:
            collection_id: Name of the collection
            vectors: List of vectors to insert
            metadata: Optional list of metadata dicts for each vector
            ids: Optional list of IDs for each vector
            **kwargs: Additional store-specific parameters
            
        Returns:
            List of inserted vector IDs
        """
        return self._dispatch("insert_vectors", collection_id, vectors, metadata, ids, **kwargs)

    def _delete_vectors(self, collection_id, ids, **kwargs):
        """Delete vectors from a collection
        
        Args:
            collection_id: Name of the collection
            ids: List of vector IDs to delete
            **kwargs: Additional store-specific parameters
            
        Returns:
            Number of vectors deleted
        """
        return self._dispatch("delete_vectors", collection_id, ids, **kwargs)

    def _search_vectors(self, collection_id, query_vector, limit=10, filter=None, **kwargs):
        """Search for similar vectors in a collection
        
        Args:
            collection_id: Name of the collection
            query_vector: Query vector to search for
            limit: Maximum number of results to return
            filter: Optional metadata filter expression
            **kwargs: Additional store-specific parameters
            
        Returns:
            List of search results (vector IDs, scores, and metadata)
        """
        return self._dispatch("search_vectors", collection_id, query_vector, limit, filter, **kwargs)

    # Index Management
    def create_index(self, collection_id, index_type=None, **kwargs):
        """Create an index on a collection
        
        Args:
            collection_id: Name of the collection
            index_type: Type of index to create
            **kwargs: Additional store-specific parameters
            
        Returns:
            Boolean indicating success
        """
        return self._dispatch("create_index", collection_id, index_type, **kwargs)
