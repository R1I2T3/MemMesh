import logging
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.tenants import Tenant
from weaviate.classes.query import Filter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from backend.config import settings

logger = logging.getLogger(__name__)
COLLECTION_NAME = "DocumentChunk"
EMBEDDING_MODEL = "models/gemini-embedding-2"
EMBEDDING_DIMENSION = 3072

class WeaviateManager:
    def __init__(self):
        self.client = weaviate.connect_to_local(
            host=settings.WEAVIATE_HOST,
            port=settings.WEAVIATE_PORT,
            grpc_port=settings.WEAVIATE_GRPC_PORT,
        )
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL, google_api_key=settings.GEMINI_API_KEY
        )

    def _get_embedding(self, text: str) -> list[float]:
        return self.embeddings.embed_query(text)

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
                Property(name="importance_score", data_type=DataType.NUMBER),
            ],
        )
        logger.info(f"Created collection {COLLECTION_NAME} with multi-tenancy")

    def create_tenant(self, team_id: str):
        collection = self.client.collections.get(COLLECTION_NAME)
        collection.tenants.create([Tenant(name=team_id)])

    def ensure_tenant(self, team_id: str):
        collection = self.client.collections.get(COLLECTION_NAME)
        tenants = collection.tenants.get()
        if team_id not in tenants:
            collection.tenants.create([Tenant(name=team_id)])
            logger.info("Created Weaviate tenant '%s'", team_id)

    def insert_chunks(self, tenant_id: str, chunks: list[dict], allowed_users: list[str]):
        self.ensure_tenant(tenant_id)
        collection = self.client.collections.get(COLLECTION_NAME).with_tenant(tenant_id)
        with collection.batch.dynamic() as batch:
            for chunk in chunks:
                text = chunk["text"]
                vector = self._get_embedding(text)
                batch.add_object(
                    vector=vector,
                    properties={
                        "text": text,
                        "parent_id": chunk["parent_id"],
                        "page_number": chunk["page_number"],
                        "bbox": chunk.get("bbox", []),
                        "dl_meta": chunk.get("dl_meta", ""),
                        "allowed_user_ids": allowed_users,
                        "importance_score": 1.0,
                    },
                )

    def hybrid_search(self, tenant_id: str, query: str, current_user_id: str, limit: int = 5) -> list[dict]:
        collection = self.client.collections.get(COLLECTION_NAME).with_tenant(tenant_id)
        query_vector = self._get_embedding(query)
        results = collection.query.hybrid(
            query=query,
            query_vector=query_vector,
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
