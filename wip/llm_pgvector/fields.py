from odoo import fields, tools
import numpy as np
from pgvector import Vector


class PgVector(fields.Field):
    """PgVector field for Odoo, using pgvector extension for PostgreSQL."""

    type = "pgvector"
    column_type = ("vector", "vector")

    _slots = {
        "dimension": None,  # Vector dimensions
    }

    def __init__(self, string=None, dimension=None, **kwargs):
        super().__init__(string=string, **kwargs)
        self.dimension = dimension

    def convert_to_column(self, value, record, values=None, validate=True):
        """Convert Python value to database format using pgvector.Vector."""
        if value is None:
            return None

        # Use Vector._to_db method from pgvector
        return Vector._to_db(value, self.dimension)

    def convert_to_cache(self, value, record, validate=True):
        """Convert database value to cache format."""
        if value is None:
            return None

        # Handle case where value is already a list or numpy array
        if isinstance(value, (list, np.ndarray)):
            return value

        # Use Vector._from_db method from pgvector for string values
        return Vector._from_db(value)

    def create_column(self, cr, table, column, **kwargs):
        """Create a vector column in the database."""
        # Register vector with this cursor
        from pgvector.psycopg2 import register_vector
        register_vector(cr)

        # Specify dimensions if provided
        dim_spec = f"({self.dimension})" if self.dimension else ""

        # Create the column with appropriate vector dimensions
        cr.execute(f"""
            ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} vector{dim_spec}
        """)

        # Update the column format to match the dimensions
        tools.set_column_type(cr, table, column, f"vector{dim_spec}")

    def create_index(self, cr, table, column, index_name, algorithm='hnsw',
                     opclass='vector_l2_ops', parameters=None):
        """Create a vector index on the column.

        Args:
            cr: Database cursor
            table: Table name
            column: Column name
            index_name: Name for the index
            algorithm: Index algorithm ('hnsw' or 'ivfflat')
            opclass: Operator class ('vector_l2_ops', 'vector_ip_ops', 'vector_cosine_ops')
            parameters: Dictionary of additional parameters for the index
        """
        # Register vector with this cursor
        from pgvector.psycopg2 import register_vector
        register_vector(cr)

        # Build the WITH clause if parameters are provided
        with_clause = ""
        if parameters:
            params = []
            for key, value in parameters.items():
                params.append(f"{key} = {value}")
            if params:
                with_clause = f" WITH ({', '.join(params)})"

        # Create the index
        cr.execute(f"""
            CREATE INDEX {index_name} ON {table} 
            USING {algorithm} ({column} {opclass}){with_clause}
        """)
        