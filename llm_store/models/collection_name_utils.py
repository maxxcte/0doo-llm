import re


class CollectionNameUtils:
    @staticmethod
    def get_collection_name(db_name, collection_id):
        return CollectionNameUtils.sanitize_collection_name(f"odoo_{db_name}_{collection_id}")

    @staticmethod
    def sanitize_collection_name(name):
        """Sanitize a collection name for Chroma"""
        # 1. Lowercase everything
        s = name.lower()

        # 2. Replace invalid chars with hyphens
        s = re.sub(r'[^a-z0-9._-]', '-', s)

        # 3. Collapse consecutive dots
        s = re.sub(r'\.{2,}', '.', s)

        # 4. Trim to max 63 chars
        s = s[:63]
        # 5. Strip non-alphanumeric from ends
        s = re.sub(r'^[^a-z0-9]+', '', s)
        s = re.sub(r'[^a-z0-9]+$', '', s)

        # 6. If too short, pad with 'a'
        if len(s) < 3:
            s = s.ljust(3, 'a')

        return s
