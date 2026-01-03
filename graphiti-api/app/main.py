"""Graphiti API - FastAPI Wrapper for Turkwise."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType
from pydantic import BaseModel
import os
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

# Logging setup
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Configuration
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD")
TURKWISE_API_KEY = os.getenv("TURKWISE_API_KEY")
TENANT_PREFIX = os.getenv("TENANT_PREFIX", "turkwise_")

# Global Graphiti client
graphiti_client: Optional[Graphiti] = None

# API Key Security
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)

async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify Turkwise API key."""
    if api_key != TURKWISE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan."""
    global graphiti_client

    # Startup: Initialize Graphiti with FalkorDB
    logger.info("Initializing Graphiti client...")

    # Create FalkorDB driver
    falkor_driver = FalkorDriver(
        host=FALKORDB_HOST,
        port=int(FALKORDB_PORT),
        password=FALKORDB_PASSWORD,
    )

    # Initialize Graphiti with driver
    graphiti_client = Graphiti(graph_driver=falkor_driver)

    # Build indices and constraints
    await graphiti_client.build_indices_and_constraints()
    logger.info("Graphiti client initialized successfully")

    yield

    # Shutdown
    if graphiti_client:
        await graphiti_client.close()
        logger.info("Graphiti client closed")


app = FastAPI(
    title="Graphiti API for Turkwise",
    description="Temporal Knowledge Graph API powered by Graphiti + FalkorDB",
    version="1.0.0",
    lifespan=lifespan,
)


# ===== MODELS =====

class EpisodeRequest(BaseModel):
    """Episode creation request."""
    tenant_id: str
    content: str
    source: str = "message"  # Valid values: "message", "text", "json"
    source_description: Optional[str] = None
    reference_time: Optional[str] = None  # ISO format datetime, defaults to now
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    """Memory search request."""
    tenant_id: str
    query: str
    limit: int = 10
    include_edges: bool = True


class EntityRequest(BaseModel):
    """Entity query request."""
    tenant_id: str
    entity_name: str


# ===== ENDPOINTS =====

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "graphiti": "connected" if graphiti_client else "disconnected",
        "falkordb": f"{FALKORDB_HOST}:{FALKORDB_PORT}",
    }


@app.post("/episodes", dependencies=[Depends(verify_api_key)])
async def add_episode(request: EpisodeRequest):
    """
    Add new episode (conversation, event, etc.) to knowledge graph.

    Multi-tenant isolation via group_id.
    """
    if not graphiti_client:
        raise HTTPException(status_code=503, detail="Graphiti not initialized")

    # Multi-tenant isolation: group_id = tenant prefix + tenant_id
    group_id = f"{TENANT_PREFIX}{request.tenant_id}"

    try:
        # Parse reference time or use current time
        ref_time = datetime.fromisoformat(request.reference_time) if request.reference_time else datetime.now()

        # Convert source string to EpisodeType enum
        try:
            source_enum = EpisodeType[request.source.lower()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid source type: {request.source}. Valid values: message, text, json")

        episodes = await graphiti_client.add_episode(
            name=request.source_description or "Customer Conversation",
            episode_body=request.content,
            source=source_enum,
            source_description=request.source_description or "",
            reference_time=ref_time,
            group_id=group_id,
        )

        logger.info(f"Episode added for tenant {request.tenant_id}")

        return {
            "success": True,
            "group_id": group_id,
            "episode": {
                "uuid": episodes.episode.uuid,
                "name": episodes.episode.name,
                "created_at": episodes.episode.created_at.isoformat() if hasattr(episodes.episode, 'created_at') else None,
            },
            "nodes_created": len(episodes.nodes),
            "edges_created": len(episodes.edges),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add episode: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", dependencies=[Depends(verify_api_key)])
async def search_memory(request: SearchRequest):
    """
    Search knowledge graph using hybrid search.

    Combines: Semantic similarity + BM25 + Graph traversal
    """
    if not graphiti_client:
        raise HTTPException(status_code=503, detail="Graphiti not initialized")

    group_id = f"{TENANT_PREFIX}{request.tenant_id}"

    try:
        results = await graphiti_client.search(
            query=request.query,
            group_ids=[group_id],
            limit=request.limit,
        )

        logger.info(f"Search completed for tenant {request.tenant_id}: {len(results)} results")

        return {
            "success": True,
            "query": request.query,
            "group_id": group_id,
            "results_count": len(results),
            "results": [
                {
                    "uuid": r.uuid,
                    "content": r.content,
                    "score": r.score if hasattr(r, 'score') else None,
                    "created_at": r.created_at.isoformat() if hasattr(r, 'created_at') else None,
                }
                for r in results
            ],
        }

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/entities/{tenant_id}", dependencies=[Depends(verify_api_key)])
async def get_entities(tenant_id: str):
    """
    Get all entities for a tenant.

    Returns semantic entities extracted from conversations.
    """
    if not graphiti_client:
        raise HTTPException(status_code=503, detail="Graphiti not initialized")

    group_id = f"{TENANT_PREFIX}{tenant_id}"

    try:
        # Search for entities using empty query to get all
        results = await graphiti_client.search(
            query="",
            group_ids=[group_id],
            num_results=1000,  # Large number to get all entities
        )

        # Extract unique entities from results
        entities_dict = {}
        for result in results:
            if hasattr(result, 'fact') and hasattr(result.fact, 'name'):
                entities_dict[result.fact.name] = {
                    "name": result.fact.name,
                    "uuid": result.fact.uuid,
                    "summary": result.fact.summary if hasattr(result.fact, 'summary') else None,
                }

        return {
            "success": True,
            "group_id": group_id,
            "entities_count": len(entities_dict),
            "entities": list(entities_dict.values()),
        }

    except Exception as e:
        logger.error(f"Get entities failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/{tenant_id}", dependencies=[Depends(verify_api_key)])
async def get_tenant_stats(tenant_id: str):
    """
    Get tenant statistics.

    Returns episode count, entity count, relationship count, etc.
    """
    if not graphiti_client:
        raise HTTPException(status_code=503, detail="Graphiti not initialized")

    group_id = f"{TENANT_PREFIX}{tenant_id}"

    try:
        # Get episodes using retrieve_episodes
        episodes = await graphiti_client.retrieve_episodes(
            reference_time=datetime.now(),
            last_n=10000,  # Large number to get all episodes
            group_ids=[group_id],
        )

        # Get entities using search
        entity_results = await graphiti_client.search(
            query="",
            group_ids=[group_id],
            num_results=10000,
        )

        # Count unique entities
        unique_entities = set()
        for result in entity_results:
            if hasattr(result, 'fact') and hasattr(result.fact, 'uuid'):
                unique_entities.add(result.fact.uuid)

        return {
            "success": True,
            "tenant_id": tenant_id,
            "group_id": group_id,
            "episodes_count": len(episodes),
            "entities_count": len(unique_entities),
        }

    except Exception as e:
        logger.error(f"Get stats failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tenant/{tenant_id}", dependencies=[Depends(verify_api_key)])
async def delete_tenant_data(tenant_id: str, confirm: bool = False):
    """
    Delete all data for a tenant.

    ⚠️ DANGEROUS: This is irreversible!
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete tenant data"
        )

    if not graphiti_client:
        raise HTTPException(status_code=503, detail="Graphiti not initialized")

    group_id = f"{TENANT_PREFIX}{tenant_id}"

    try:
        # Clear all data for this group_id
        await graphiti_client.clear_data(group_id=group_id)

        logger.warning(f"Tenant data deleted: {tenant_id}")

        return {
            "success": True,
            "message": f"All data deleted for tenant {tenant_id}",
            "group_id": group_id,
        }

    except Exception as e:
        logger.error(f"Delete tenant failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
