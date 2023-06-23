import logging
import numpy as np

from odoo import fields, tools
from pgvector.psycopg2 import register_vector

_logger = logging.getLogger(__name__)


class PgVector(fields.Field):
    """
    Vector field for Odoo, using pgvector extension for PostgreSQL.
    Supports variable dimensions for vectors.
    """

    type = "pgvector"
    column_type = ("vector", "vector")
    column_cast_from = ("varchar", "text")

    def convert_to_column(self, value, record, values=None, validate=True):
        """Convert Python value to database format."""
        if value is None:
            return None

        # Convert list or numpy array to vector format for PostgreSQL
        if isinstance(value, list):
            # Check if we have a nested list and flatten it
            if value and isinstance(value[0], list):
                value = value[0]  # Take the first inner list
            return f"[{','.join(map(str, value))}]"
        elif isinstance(value, np.ndarray):
            # Ensure we're dealing with a 1D array
            if value.ndim > 1:
                value = value.flatten()
            return f"[{','.join(map(str, value.tolist()))}]"
        else:
            raise ValueError("Vector value must be a list or numpy array")

    def convert_to_cache(self, value, record, validate=True):
        """Convert database value to cache format."""
        if value is None:
            return None

        # Convert to list for cache storage
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def create_column(self, cr, table, column, **kwargs):
        """Create a vector column in the database without fixed dimensions."""
        # Register vector with this cursor
        register_vector(cr)

        # Create the column with dynamic vector dimensions
        # Note: Not specifying dimensions allows for variable-length vectors
        cr.execute(f"""
            ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} vector
        """)

        # Update the column format to match vector type
        tools.set_column_type(cr, table, column, "vector")

    def create_index(self, cr, table, column, index_name, dimensions=None, model_field_name=None, model_id=None):
        """
        Create a vector index for the specified column.
        
        Args:
            cr: Database cursor
            table: Table name
            column: Column name
            index_name: Name for the index
            dimensions: Vector dimensions (optional)
            model_field_name: Field name that stores model information (optional)
            model_id: Model ID to filter by (optional)
        """
        # Register vector with this cursor
        register_vector(cr)

        # Drop existing index if it exists
        cr.execute(f"DROP INDEX IF EXISTS {index_name}")

        # Determine the dimension specification
        dim_spec = f"({dimensions})" if dimensions else ""
        
        # Create the appropriate index with or without model filtering
        if model_field_name and model_id:
            # Create model-specific index
            cr.execute(f"""
                CREATE INDEX {index_name} ON {table}
                USING hnsw(({column}::vector{dim_spec}) vector_cosine_ops)
                WHERE {model_field_name} = %s AND {column} IS NOT NULL
            """, (model_id,))
        else:
            # Create general index
            cr.execute(f"""
                CREATE INDEX {index_name} ON {table}
                USING hnsw(({column}::vector{dim_spec}) vector_cosine_ops)
                WHERE {column} IS NOT NULL
            """)
            
        _logger.info(f"Created vector index {index_name} on {table}.{column}")

    def drop_index(self, cr, index_name):
        """Drop a vector index by name."""
        cr.execute(f"DROP INDEX IF EXISTS {index_name}")
        _logger.info(f"Dropped vector index {index_name}")
