import os
import re
import uuid
import json
import logging
from typing import List, Dict, Any, Optional

import lancedb
import pyarrow as pa

logger = logging.getLogger(__name__)

# Enterprise-grade schema for Memory Mesh
# Includes flexible metadata JSON to support graph attributes without schema migrations
SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("embedding", pa.list_(pa.float32(), 768)),
        pa.field("source", pa.string()),
        pa.field("chunk_index", pa.int32()),
        pa.field("metadata", pa.string()),  # JSON encoded metadata
    ]
)


class VectorStore:
    def __init__(self, path: Optional[str] = None, table_name: str = "memory_chunks"):
        """
        Initializes the LanceDB vector store built for high-throughput AI memory.
        """
        self.uri = path or os.getenv("LANCEDB_PATH", "./data/lancedb")

        # Ensure the directory exists if not using an object store like MinIO or AWS S3
        if not self.uri.startswith(("s3://", "minio://")):
            os.makedirs(
                os.path.dirname(self.uri) if os.path.dirname(self.uri) else ".",
                exist_ok=True,
            )

        self.db = lancedb.connect(self.uri)
        self.table_name = table_name

        if self.table_name in self.db.table_names():
            self.table = self.db.open_table(self.table_name)
        else:
            self.table = self.db.create_table(self.table_name, schema=SCHEMA)

    def insert(self, chunks: List[Dict[str, Any]]):
        """
        Inserts document chunks into the database.
        Automatically processes ID generation and serializes extra keys into `metadata`.
        """
        if not chunks:
            logger.warning("Empty chunk list provided for insertion.")
            return

        formatted_records = []
        for chunk in chunks:
            # Deterministic namespace hashing for idempotency if ID missing
            record_id = chunk.get("id") or str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{chunk.get('source', '')}_{chunk.get('chunk_index', 0)}_{hash(chunk.get('text', ''))}",
                )
            )

            # Extract standard explicitly typed fields
            text = chunk.get("text", "")
            embedding = chunk.get("embedding", [])
            source = chunk.get("source", "unknown")
            chunk_index = chunk.get("chunk_index", -1)

            # Package remaining keys into metadata json blob
            metadata_dict = {
                k: v
                for k, v in chunk.items()
                if k not in ["id", "text", "embedding", "source", "chunk_index"]
            }

            formatted_records.append(
                {
                    "id": record_id,
                    "text": text,
                    "embedding": embedding,
                    "source": source,
                    "chunk_index": chunk_index,
                    "metadata": json.dumps(metadata_dict),
                }
            )

        self.table.add(formatted_records)
        logger.info(f"Inserted {len(formatted_records)} memory chunks.")

    def search(
        self, query_vector: List[float], top_k: int = 5, where: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs an Approximate Nearest Neighbor (ANN) search.
        Supports relational cross-filtering through `where` clauses.
        """
        if self.table.count_rows() == 0:
            return []

        search_query = self.table.search(query_vector).limit(top_k)

        if where:
            search_query = search_query.where(where)

        results = search_query.to_list()

        # Deserialize JSON metadata back into dictionaries for the caller
        for r in results:
            if "metadata" in r and isinstance(r["metadata"], str):
                try:
                    r["metadata"] = json.loads(r["metadata"])
                except json.JSONDecodeError:
                    pass
        return results

    def search_by_id(self, record_id: str) -> List[Dict[str, Any]]:
        """Retrieves a specific chunk record directly by ID mapping."""
        if self.table.count_rows() == 0:
            return []

        # Validate record_id is a proper UUID to prevent injection
        if not re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            record_id,
            re.IGNORECASE,
        ):
            logger.warning(f"Invalid record_id format: {record_id}")
            return []

        results = self.table.search().where(f"id = '{record_id}'").to_list()
        for r in results:
            if "metadata" in r and isinstance(r["metadata"], str):
                try:
                    r["metadata"] = json.loads(r["metadata"])
                except json.JSONDecodeError:
                    pass
        return results
