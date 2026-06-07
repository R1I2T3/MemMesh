import logging
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.tenants import Tenant
from weaviate.classes.query import Filter
from backend.config import settings

logger = logging.getLogger(__name__)
COLLECTION_NAME = "DocumentChunk"

class WeaviateManager:
    def __init__(self):
        self.client = weaviate.connect_to_local(
            host=settings.WEAVIATE_HOST,
            port=settings.WEAVIATE_PORT,
            grpc_port=settings.WEAVIATE_GRPC_PORT,
        )

    def ensure_schema(self):
        if self.client.collections.exists(COLLECTION_NAME):
            return
        self.client.collections.create(
            name=COLLECTION_NAME,
            multi_tenancy_config=Configure.multi_tenancy(enabled=True),
            properties=[
                Property(name="text", data_type=DataType.TEXT),
                Property(name="parent_id", data_type=DataType.TEXT),
                Property(name="page_number", data_type=DataType.INT),
                Property(name="bbox", data_type=DataType.NUMBER_ARRAY),
                Property(name="dl_meta", data_type=DataType.TEXT),
                Property(name="allowed_user_ids", data_type=DataType.TEXT_ARRAY),
            ],
        )
        logger.info(f"Created collection {COLLECTION_NAME} with multi-tenancy")

    def create_tenant(self, team_id: str):
        collection = self.client.collections.get(COLLECTION_NAME)
        collection.tenants.create([Tenant(name=team_id)])

    def insert_chunks(self, tenant_id: str, chunks: list[dict], allowed_users: list[str]):
        collection = self.client.collections.get(COLLECTION_NAME).with_tenant(tenant_id)
        with collection.batch.dynamic() as batch:
            for chunk in chunks:
                batch.add_object(properties={
                    "text": chunk["text"],
                    "parent_id": chunk["parent_id"],
                    "page_number": chunk["page_number"],
                    "bbox": chunk.get("bbox", []),
                    "dl_meta": chunk.get("dl_meta", ""),
                    "allowed_user_ids": allowed_users,
                })

    def hybrid_search(self, tenant_id: str, query: str, current_user_id: str, limit: int = 5) -> list[dict]:
        collection = self.client.collections.get(COLLECTION_NAME).with_tenant(tenant_id)
        results = collection.query.hybrid(
            query=query,
            alpha=0.5,
            filters=Filter.by_property("allowed_user_ids").contains_any([current_user_id, "public"]),
            limit=limit,
        )
        return [
            {
                "text": o.properties.get("text", ""),
                "parent_id": o.properties.get("parent_id", ""),
                "page_number": o.properties.get("page_number", 0),
                "bbox": o.properties.get("bbox", []),
                "dl_meta": o.properties.get("dl_meta", ""),
            }
            for o in results.objects
        ]

    def close(self):
        self.client.close()

_weaviate_mgr = None

def get_weaviate_mgr() -> WeaviateManager:
    global _weaviate_mgr
    if _weaviate_mgr is None:
        _weaviate_mgr = WeaviateManager()
    return _weaviate_mgr
