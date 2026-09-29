# JSON API Specification

## Overview
All API responses follow the standard envelope below. Frontend and backend should agree on these fields to avoid frequent interface changes.

## Standard Response Envelope

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "request_id": "req_1715678880000_12345",
  "timestamp": 1715678880,
  "data": {
    "question": "用户问题",
    "answer": "答案内容",
    "expanded_query": "扩展后的query",
    "from_cache": true,
    "latency_ms": 123,
    "show_sources": false,
    "sources": [],
    "cache_info": {
      "capacity": 128,
      "size": 12,
      "hits": 5,
      "misses": 7,
      "hit_rate_pct": 41.67,
      "ttl_seconds": 3600
    }
  }
}
```

## Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| success | bool | Overall request success |
| code | string | Business code: OK / ERR_* |
| message | string | Human-readable message |
| request_id | string | Unique request identifier |
| timestamp | int | Unix timestamp (seconds) |
| data | object/null | Payload container |

## `data` Object

| Field | Type | Description |
|-------|------|-------------|
| question | string | Original user question |
| answer | string | Generated answer |
| expanded_query | string | Synonym-expanded query (for debug) |
| from_cache | bool | Whether served from cache |
| latency_ms | int | Total latency in milliseconds |
| show_sources | bool | Whether sources are included |
| sources | array | List of source documents (when show_sources=true) |
| cache_info | object | Cache statistics |

## Source Object (when show_sources=true)

```json
{
  "source_file": "10_air_rifle.md",
  "snippet": "10米气步枪资格赛男子和女子的发数均为60发...",
  "rerank_score": 0.9234
}
```

## Error Envelope

```json
{
  "success": false,
  "code": "ERR_VECTOR_SEARCH",
  "message": "向量库检索异常: ...",
  "request_id": "req_xxx",
  "timestamp": 1715678880,
  "data": null
}
```

## Common Error Codes

- ERR_INVALID_JSON: JSON parse failed
- ERR_INVALID_PAYLOAD: payload not dict
- ERR_NOT_INIT: Service not initialized
- ERR_EMPTY_QUESTION: Empty question
- ERR_NO_API_KEY: Missing/invalid API key
- ERR_VECTOR_STORE: Vector store load/build failed
- ERR_VECTOR_SEARCH: Retrieval exception
- ERR_RAG_EXCEPTION: LLM/generation exception
- SERVER_ERROR: Unhandled server error

## Interfaces

### POST /api/ask
Request body:
```json
{
  "question": "10米气步枪决赛多少发？",
  "use_cache": true,
  "show_sources": false
}
```

### GET /api/health
Response:
```json
{
  "success": true,
  "code": "OK",
  "message": "服务正常",
  "timestamp": 1715678880,
  "data": {
    "llm_model": "qwen-plus",
    "embedding_model": "text-embedding-v2",
    "rerank_enabled": true,
    "cache": { ... }
  }
}
```
