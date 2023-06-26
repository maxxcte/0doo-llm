import numpy as np
from pgvector.psycopg2 import register_vector

from odoo import fields, tools


class PgVector(fields.Field):
    """PgVector field for Odoo, using pgvector extension for PostgreSQL."""

    type = "pgvector"
    column_type = ("vector", "vector")
    column_cast_from = ("varchar", "text")

    _slots = {
        "dimension_field": None,  # Field name that stores the dimension information
        "default_dimensions": None,  # Default dimensions if not specified elsewhere
    }

    def __init__(
        self, string=None, dimension_field=None, default_dimensions=None, **kwargs
    ):
        super().__init__(string=string, **kwargs)
        self.dimension_field = dimension_field
        self.default_dimensions = default_dimensions

    def _setup_regular_full(self, model):
        super()._setup_regular_full(model)
        if not self.dimension_field and not self.default_dimensions:
            raise ValueError(
                f"Field {self}: Either 'dimension_field' or 'default_dimensions' must be provided for pgvector fields"
            )

    def convert_to_column(self, value, record, values=None, validate=True):
        if value is None:
            return None

        # Convert list or numpy array to vector format for PostgreSQL
        if isinstance(value, list):
            # Check if we have a nested list (the error case) and flatten it
            if value and isinstance(value[0], list):
                value = value[0]  # Take the first (and should be only) inner list
            return f"[{','.join(map(str, value))}]"
        elif isinstance(value, np.ndarray):
            # Ensure we're dealing with a 1D array
            if value.ndim > 1:
                value = value.flatten()
            return f"[{','.join(map(str, value.tolist()))}]"
        else:
            raise ValueError("Vector value must be a list or numpy array")

    def convert_to_cache(self, value, record, validate=True):
        if value is None:
            return None

        # Convert to list for cache storage
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def create_column(self, cr, table, column, value_field=None, **kwargs):
        # Register vector with this cursor
        register_vector(cr)

        # Determine dimensions for this field
        dimensions = self.default_dimensions

        if self.dimension_field:
            # Dynamically determine the dimension based on the dimension_field
            cr.execute(f"""
                SELECT DISTINCT({self.dimension_field})
                FROM {table}
                WHERE {self.dimension_field} IS NOT NULL
                LIMIT 1
            """)
            result = cr.fetchone()
            if result and result[0]:
                dimensions = result[0]

        if not dimensions:
            dimensions = 1536  # Default fallback to standard OpenAI dimensions

        # Create the column with appropriate vector dimensions
        column_format = f"vector({dimensions})"

        # Use PostgreSQL to create the column
        cr.execute(f"""
            ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {column_format}
        """)

        # Update the column format to match the dimensions if needed
        tools.set_column_type(cr, table, column, column_format)

    def create_indices(self, cr, table, column):
        """Create multiple indices based on different embedding models"""
        # Register vector with this cursor
        register_vector(cr)

        if not self.dimension_field:
            # If no dimension field is specified, create a standard index
            index_name = f"{table}_{column}_idx"

            # Drop existing index first if it exists
            cr.execute(f"DROP INDEX IF EXISTS {index_name}")

            # Create new HNSW index
            cr.execute(f"""
                CREATE INDEX {index_name} ON {table}
                USING hnsw({column} vector_cosine_ops)
                WHERE {column} IS NOT NULL
            """)
            return

        # Get distinct values of the dimension field to create separate indices
        cr.execute(f"""
            SELECT DISTINCT {self.dimension_field}
            FROM {table}
            WHERE {self.dimension_field} IS NOT NULL
        """)

        model_ids = cr.fetchall()

        for model_id in model_ids:
            if not model_id[0]:
                continue

            # Create a model-specific index
            # Use a unique index name, including model ID
            index_name = f"{table}_{column}_model_{model_id[0]}_idx"

            # Drop existing index first if it exists
            cr.execute(f"DROP INDEX IF EXISTS {index_name}")

            # Create new HNSW index filtered for this model
            cr.execute(
                f"""
                CREATE INDEX {index_name} ON {table}
                USING hnsw({column} vector_cosine_ops)
                WHERE {self.dimension_field} = %s AND {column} IS NOT NULL
            """,
                (model_id[0],),
            )
