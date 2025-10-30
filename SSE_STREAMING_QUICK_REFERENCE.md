# SSE Streaming & State Management - Quick Reference

## Key Findings

### 1. Page Refresh During Agent Execution
- **Auto-detected**: On mount, checks if last system message has `status='in_progress'`
- **Auto-recovery**: Immediately starts polling every 1.2s
- **UI Feedback**: "Loading… showing recent progress" banner appears
- **Duration**: Polls for up to 2 minutes

### 2. State Persistence
All critical state persisted in database:
- **Completion** table: `status`, `sigkill` timestamp, `completion` JSON content
- **CompletionBlock** table: `status`, `content`, `reasoning`, `started_at`, `completed_at`
- **AgentExecution** table: `status`, `latest_seq` (for future resume), error_json

### 3. Streaming Architecture
- **Active**: SSE events streamed via `/api/reports/{id}/completions?stream=true`
- **Fallback**: HTTP polling via `GET /api/reports/{id}/completions`
- **No SSE Resumption**: Currently uses polling-based recovery (simple, stateless)

### 4. Status Lifecycle
```
User Creates → 'in_progress' → 'success'/'error'/'stopped'
                    ↓
            CompletionBlocks stream with status updates
```

### 5. Recovery Mechanisms
1. **Polling** (Primary): Every 1.2s for 2 minutes after refresh
2. **User Stop**: POST `/api/completions/{id}/sigkill` to stop agent
3. **Database Backup**: All state always recoverable from DB
4. **Error Handling**: Distinguishes user-stop from network errors

### 6. Reconnection Logic
- **Normal Stream Error**: Mark as 'error', add error block
- **User Stop**: Mark as 'stopped', no error block
- **Network Break During Stream**: Could start polling (not automatic)
- **Page Refresh**: Auto-starts polling immediately

### 7. Cursor Pagination (NOT Event-Based Resume)
- Frontend: `cursorBefore` ISO datetime cursor
- Backend: `next_before` in response, `before` query param
- For paginating through older completions (not for SSE resume)
- AgentExecution.latest_seq available but unused

### 8. Error Classification
| Error | Response |
|-------|----------|
| User clicks stop | AbortController.abort() + sigkill POST |
| Network disconnect | Catch AbortError, could start polling |
| HTTP error | Mark as error, add error block |
| Page refresh | Auto-start polling |
| Timeout (2min) | Stop polling, user must refresh |

## Key Code Locations

| Concept | File | Lines |
|---------|------|-------|
| Completion model + hooks | backend/app/models/completion.py | 21-213 |
| Polling on refresh | frontend/pages/reports/[id]/index.vue | 1690-1737, 1739-1791 |
| SSE streaming | backend/app/services/completion_service.py | 793-1046 |
| Stream events handler | frontend/pages/reports/[id]/index.vue | 736-1120 |
| Sigkill (user stop) | backend/app/services/completion_service.py | 1058-1087 |
| Error handling | frontend/pages/reports/[id]/index.vue | 1639-1688 |
| Completions endpoint | backend/app/routes/completion.py | 29-70, 108-123 |
| Event queue | backend/app/streaming/completion_stream.py | 1-29 |
| SSE schema | backend/app/schemas/sse_schema.py | 1-31 |

## Important Limitations

1. **2-minute polling limit**: After 2 min, polling stops. User must refresh.
2. **1.2s poll interval**: Up to 1.2s latency on page refresh
3. **No automatic reconnection**: Network break requires manual refresh
4. **No SSE resumption**: Could implement latest_seq tracking but currently unused

## Performance Notes

- Polling uses cursor pagination (efficient DB queries)
- SSE uses event queue (no buffer bloat)
- Block deltas streamed with tokens (typing effect)
- Periodic snapshots (every 1.2s) for robustness

## Testing Scenarios

1. **Normal flow**: Submit → Stream → Complete ✓
2. **Page refresh**: Refresh during streaming → Polling takes over ✓
3. **Network break**: Disconnect → Mark stopped (user can refresh to recover) ✓
4. **User stop**: Click stop → Sigkill sent, blocks marked stopped ✓
5. **Very long agent**: After 2 min, polling stops (manual refresh needed) ⚠️

