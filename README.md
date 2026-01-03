# Graphiti + FalkorDB Stack for Turkwise

Temporal Knowledge Graph API powered by **Graphiti** and **FalkorDB**, deployed on **Coolify**.

## Features

- **Multi-Tenant Knowledge Graph**: Isolated data per tenant using group_id
- **Temporal Memory**: Track conversations, events, and relationships over time
- **Hybrid Search**: Semantic similarity + BM25 + Graph traversal
- **Production-Ready**: Health checks, logging, monitoring, auto-recovery
- **Secure**: API key authentication, non-root containers, encrypted connections

## Architecture

```
┌─────────────────┐
│  Graphiti API   │  FastAPI (Python 3.11)
│  Port: 8000     │  - Episodes, Search, Entities
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    FalkorDB     │  Graph Database (Redis Protocol)
│  Port: 6379     │  - Knowledge graph storage
└─────────────────┘
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Add Episode (Conversation/Event)
```bash
POST /episodes
Headers: X-API-KEY: <your-api-key>
Body: {
  "tenant_id": "merchant_001",
  "content": "Customer conversation text...",
  "episode_type": "conversation",
  "source_description": "WhatsApp Chat"
}
```

### Search Memory
```bash
POST /search
Headers: X-API-KEY: <your-api-key>
Body: {
  "tenant_id": "merchant_001",
  "query": "product delivery",
  "limit": 10
}
```

### Get Entities
```bash
GET /entities/{tenant_id}
Headers: X-API-KEY: <your-api-key>
```

### Get Tenant Stats
```bash
GET /stats/{tenant_id}
Headers: X-API-KEY: <your-api-key>
```

### Delete Tenant Data (⚠️ Dangerous)
```bash
DELETE /tenant/{tenant_id}?confirm=true
Headers: X-API-KEY: <your-api-key>
```

## Deployment on Coolify

### Prerequisites
1. Coolify instance running
2. GitHub account
3. OpenAI API key
4. Domain or subdomain for the API

### Step 1: Environment Variables

Required variables (set in Coolify UI):

```env
FALKORDB_PASSWORD=<secure-password-min-16-chars>
OPENAI_API_KEY=sk-proj-xxxxx
TURKWISE_API_KEY=<your-secure-api-key>
```

Optional variables:
```env
GRAPHITI_LLM_PROVIDER=openai
GRAPHITI_LLM_MODEL=gpt-4o
GRAPHITI_EMBEDDER_PROVIDER=openai
GRAPHITI_EMBEDDER_MODEL=text-embedding-3-small
SEMAPHORE_LIMIT=10
WORKER_COUNT=4
LOG_LEVEL=INFO
```

### Step 2: Coolify Deployment

1. **Create New Application**
   - Go to Coolify Dashboard → Projects → Turkwise Hub
   - Click "Create New Resource" → Application
   - Select "GitHub App" as source

2. **Repository Settings**
   - Repository: `<your-github-username>/graphiti-stack`
   - Branch: `main`
   - Build Pack: **Docker Compose**
   - Docker Compose Location: `docker-compose.yml` (or leave empty if in root)

3. **Environment Variables**
   - Go to "Environment Variables" tab
   - Add all required variables (marked with red border in UI)
   - Save

4. **Domain Assignment**
   - Go to "Services" tab
   - Click on `graphiti-api` service
   - Add domain or use Coolify auto-generated subdomain
   - HTTPS will be enabled automatically

5. **Deploy**
   - Click "Deploy" button
   - Monitor logs in "Logs" tab
   - Wait for health checks to pass (30-40 seconds)

6. **Verify Deployment**
   ```bash
   curl https://<your-domain>/health
   ```

   Expected response:
   ```json
   {
     "status": "healthy",
     "graphiti": "connected",
     "falkordb": "falkordb:6379"
   }
   ```

## Multi-Tenant Isolation

Each tenant's data is isolated using `group_id`:

```
group_id = "turkwise_" + tenant_id
```

Example:
- Tenant: `merchant_001` → group_id: `turkwise_merchant_001`
- Tenant: `merchant_002` → group_id: `turkwise_merchant_002`

Tenants **cannot** access each other's data.

## Storage & Backup

- **Volume**: `falkordb_data` (persistent storage)
- **Backup**: Enable in Coolify UI → Storage tab
- **Schedule**: Daily 2:00 AM (recommended)

## Monitoring

### Health Checks
- **FalkorDB**: `redis-cli ping` every 10s
- **Graphiti API**: `curl /health` every 30s

### Metrics to Monitor
- FalkorDB memory usage (2GB limit)
- Query latency (target: <200ms)
- Error rate (target: <1%)
- OpenAI API rate limits

## Troubleshooting

### "Docker Compose file is empty"
- Ensure `docker-compose.yml` exists in repository root
- Check file name is exactly `docker-compose.yml`
- Verify file is committed to GitHub

### "Required environment variables not set"
- Check Coolify UI → Environment Variables tab
- Ensure all variables with `:?` suffix are set:
  - `FALKORDB_PASSWORD`
  - `OPENAI_API_KEY`
  - `TURKWISE_API_KEY`

### Services not starting
```bash
# Check logs in Coolify UI
# Or connect to Coolify server and run:
docker logs falkordb
docker logs graphiti-api
```

### Health check failing
```bash
# Test FalkorDB connection
docker exec -it falkordb redis-cli -a <FALKORDB_PASSWORD> ping
# Expected: PONG
```

## Development

### Local Testing
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Test API
```bash
# Add episode
curl -X POST http://localhost:8000/episodes \
  -H "X-API-KEY: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "test_001",
    "content": "Test conversation"
  }'

# Search
curl -X POST http://localhost:8000/search \
  -H "X-API-KEY: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "test_001",
    "query": "test"
  }'
```

## Documentation

- [Graphiti Documentation](https://github.com/getzep/graphiti)
- [FalkorDB Documentation](https://docs.falkordb.com/)
- [Coolify Documentation](https://coolify.io/docs/)

## License

MIT

## Support

For issues or questions, please open an issue on GitHub or contact Turkwise support.
