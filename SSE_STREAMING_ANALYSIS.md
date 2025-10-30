# SSE Streaming, Disconnection, and State Management in bagofwords

## Overview

bagofwords implements a sophisticated SSE (Server-Sent Events) streaming system for agent execution with built-in resilience mechanisms for page refreshes, disconnections, and state recovery. The system uses a multi-layered approach combining:

1. **SSE (Server-Sent Events)** for real-time streaming of agent execution
2. **Database-backed state persistence** for all in-progress completions
3. **Polling fallback mechanism** for refresh/disconnection recovery
4. **Status tracking** across multiple tables (Completion, CompletionBlock, AgentExecution)
5. **Event sourcing** via SSE event queue with sequence numbering

---

## 1. What Happens When a User Refreshes the Page During Agent Execution?

### Frontend Behavior (pages/reports/[id]/index.vue)

**On Mount (lines 1739-1791):**
```vue
onMounted(async () => {
  await Promise.all([
    loadReport(),
    loadVisualizations(),
    loadCompletions(),  // Loads all completions including in-progress ones
    loadActiveLayoutHasBlocks()
  ])
  
  // CRITICAL: After loading, check if any system message is still in progress
  if (!isStreaming.value && getLastInProgressSystem()) {
    startPollingInProgressCompletion()  // Automatically resume polling!
  }
})
```

**Key Flow:**
1. **loadCompletions()** fetches all completions from `/reports/{id}/completions` endpoint
2. The endpoint returns completions with their full **state** including:
   - `status`: 'in_progress', 'success', 'error', 'stopped'
   - `sigkill`: timestamp if the completion was manually stopped
   - `completion_blocks`: array of all blocks generated so far
3. **Auto-detect in-progress**: Checks if the last system message has `status === 'in_progress'`
4. **Automatically resume polling**: Calls `startPollingInProgressCompletion()` to poll the backend every 1.2 seconds

### Backend Completions Endpoint (completion_service.py, routes/completion.py)

**GET /api/reports/{report_id}/completions** (lines 108-123 in completion.py):
```python
async def get_completions_v2(
    report_id: str,
    limit: int = 10,
    before: str | None = None,
    ...
):
    # Returns last N completions with cursor pagination
    return await completion_service.get_completions_v2(
        db, report_id, organization, current_user, limit=limit, before=before
    )
```

**Response includes:**
- `completions`: Array of CompletionV2Schema objects
- `has_more`: Boolean for pagination
- `next_before`: ISO datetime cursor for older completions
- `total_completions`, `total_blocks`, `total_widgets_created`, `total_steps_created`

---

## 2. State Persistence for In-Progress Completions

### Completion Model Status Fields (models/completion.py)

```python
class Completion(BaseSchema):
    status = Column(String, nullable=False, default='success')  # 'success', 'in_progress', 'error', 'stopped'
    completion = Column(JSON, nullable=False, default="")  # The actual content being streamed
    prompt = Column(JSON, nullable=False, default="")  # User's prompt
    sigkill = Column(DateTime, nullable=False, default=None)  # Timestamp when stopped
    role = Column(String, nullable=False, default='system')  # 'user' or 'system'
    message_type = Column(String, nullable=False, default='ai_completion')
    
    # Relationships for full context
    report = relationship("Report", back_populates="completions")
    completions_blocks = relationship("CompletionBlock")
    mentions = relationship("Mention")
    feedbacks = relationship("CompletionFeedback")
```

### CompletionBlock Status Tracking (models/completion_block.py)

```python
class CompletionBlock(BaseSchema):
    status = Column(String, nullable=False, default='in_progress')  # 'in_progress', 'completed', 'success', 'error', 'stopped'
    content = Column(String, nullable=True)  # Denormalized content for fast UI
    reasoning = Column(String, nullable=True)  # Denormalized reasoning
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Links to source data
    plan_decision_id = Column(String(36), ForeignKey('plan_decisions.id'))
    tool_execution_id = Column(String(36), ForeignKey('tool_executions.id'))
```

### AgentExecution Tracking (models/agent_execution.py)

```python
class AgentExecution(BaseSchema):
    status = Column(String, nullable=False, default='in_progress')  # 'in_progress', 'success', 'error'
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    total_duration_ms = Column(Float, nullable=True)
    first_token_ms = Column(Float, nullable=True)
    thinking_ms = Column(Float, nullable=True)
    
    # CRITICAL for streaming resume:
    latest_seq = Column(Integer, nullable=False, default=0)  # Latest event sequence number
    
    # For recovery:
    error_json = Column(JSON, nullable=True)  # Error details if failed
    token_usage_json = Column(JSON, nullable=True)  # Token tracking
```

### Database Event Hooks (models/completion.py)

```python
def after_insert_completion(mapper, connection, target):
    """Triggers database update event whenever completion is created"""
    data = {
        "event": "insert_completion",
        "id": str(target.id),
        "status": target.status,
        "completion": target.completion,
        ...
    }
    asyncio.create_task(broadcast_event(data))  # Broadcast via WebSocket

def after_update_completion(mapper, connection, target):
    """Triggers whenever completion status changes"""
    data = {
        "event": "update_completion",
        "status": target.status,
        ...
    }
    asyncio.create_task(broadcast_event(data))

# Register event listeners
event.listen(Completion, 'after_insert', after_insert_completion)
event.listen(Completion, 'after_update', after_update_completion)
```

---

## 3. SSE Stream Resumption/Reconnection Capability

### Current Architecture: No SSE Resumption - Polling-Based Recovery

**Important Finding:** SSE streams are **NOT** resumable. Instead, bagofwords uses:

1. **SSE for streaming** while client is actively connected
2. **Polling for recovery** when client disconnects/refreshes

### Frontend Polling Mechanism (pages/reports/[id]/index.vue, lines 1690-1737)

```typescript
// === Minimal polling for refresh resume (no SSE resume) ===
const isPolling = ref<boolean>(false)
const pollIntervalMs = 1200  // Poll every 1.2 seconds

function getLastInProgressSystem(): ChatMessage | undefined {
  return [...messages.value].reverse().find(m => m.role === 'system' && m.status === 'in_progress')
}

async function startPollingInProgressCompletion() {
  if (isStreaming.value || isPolling.value) return
  const sys = getLastInProgressSystem()
  if (!sys) return

  isPolling.value = true
  const startTs = Date.now()
  const maxDurationMs = 2 * 60 * 1000  // Max poll for 2 minutes

  const tick = async () => {
    try {
      await loadCompletions()  // Fetch latest state from backend
      autoScrollIfNearBottom()
      const still = getLastInProgressSystem()
      if (!still) {  // Completion finished
        stopPollingInProgressCompletion()
        return
      }
      if (Date.now() - startTs > maxDurationMs) {  // Timeout after 2 min
        stopPollingInProgressCompletion()
        return
      }
    } catch (e) {
      // keep polling on transient errors
    } finally {
      pollHandle = window.setTimeout(tick, pollIntervalMs)  // Schedule next poll
    }
  }

  pollHandle = window.setTimeout(tick, pollIntervalMs)
}
```

**Polling Recovery UI (lines 264-270):**
```vue
<!-- Minimal reconnect banner while polling after refresh (bottom, above prompt) -->
<div v-if="isPolling" class="mx-auto px-4 mt-2 mb-2" :class="isSplitScreen ? 'w-full' : 'md:w-1/2 w-full'">
  <div class="text-xs text-gray-500 flex items-center">
    <Spinner class="w-3 h-3 mr-2 text-gray-400" />
    <span class="poll-shimmer">Loading… showing recent progress</span>
  </div>
</div>
```

### Why Polling Instead of SSE Resumption?

**Advantages:**
- Simple and reliable - no need for server-side event ID tracking
- Works across network transitions
- Automatic state recovery from database
- Stateless for server (scales horizontally)

**Limitations:**
- Higher latency during refresh (up to 1.2 seconds)
- Polling timeout limits recovery to 2 minutes

---

## 4. Completion Status Lifecycle Tracking

### Status State Machine

```
┌─────────────────────────────────────────────────────────┐
│ Completion Status Lifecycle                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [User Creates] → 'in_progress' (system_completion)    │
│         ↓                                               │
│  [Agent Executing] → blocks stream (CompletionBlocks)  │
│         ↓                                               │
│  [Agent Finishes] → 'success' or 'error'              │
│         ↓                                               │
│  [User Stops] → 'stopped' + sigkill timestamp          │
│                                                         │
└─────────────────────────────────────────────────────────┘

Block Status Sub-lifecycle:
  'in_progress' → 'completed'|'success'|'error'|'stopped'
```

### Completion Statuses

| Status | Meaning | Source | Frontend Display |
|--------|---------|--------|------------------|
| `in_progress` | Agent is executing | CompletionService.create_completion_stream() | Streaming dots, polling banner |
| `success` | Completed normally | Agent.main_execution() finished | All blocks rendered |
| `error` | Failed during execution | Exception in agent flow | Error block with message |
| `stopped` | User manually stopped | sigkill endpoint | "Generation stopped" UI |

### Block Statuses

| Status | Meaning |
|--------|---------|
| `in_progress` | Block being generated |
| `completed` | Block finished (research blocks) |
| `success` | Tool execution succeeded |
| `error` | Tool execution failed |
| `stopped` | Block generation interrupted by user |

### Frontend Status Detection (pages/reports/[id]/index.vue, lines 1129-1132)

```typescript
let status = c.status as ChatStatus
if (c.sigkill && status === 'in_progress') {
  // Completion was stopped - override status
  status = 'stopped'
}
```

---

## 5. Recovery Mechanisms

### A. Automatic Polling on Page Refresh

**Trigger:** Page mount detects `in_progress` completion → starts polling
**Duration:** Up to 2 minutes
**Interval:** Every 1.2 seconds
**UI Feedback:** "Loading… showing recent progress" banner

### B. SSE Streaming During Active Session

**Endpoint:** `/api/reports/{report_id}/completions` with `stream: true`
**Mechanism:** Server sends SSEEvent objects as they're generated
**Events:**
```python
# From completion_service.py, create_completion_stream()
SSEEvent(
    event="completion.started",
    completion_id=str(completion.id),
    data={"system_completion_id": str(system_completion.id)}
)

SSEEvent(
    event="block.upsert",
    completion_id=str(system_completion.id),
    data={"block": {...}}
)

SSEEvent(
    event="block.delta.token",  # Individual token stream
    data={"block_id": "...", "field": "content", "token": "..."}
)

SSEEvent(
    event="completion.finished",
    completion_id=str(completion.id),
    data={"status": "success"}
)
```

### C. User-Initiated Stop (Sigkill)

**Frontend Abort (pages/reports/[id]/index.vue, lines 1444-1483):**
```typescript
function abortStream() {
  if (currentController) {
    currentController.abort()  // Abort fetch stream
    currentController = null
  }
  
  // Signal backend to stop
  const sysMsg = [...messages.value].reverse().find(m => m.role === 'system' && m.status === 'in_progress')
  const systemId = (sysMsg as any)?.system_completion_id
  if (systemId) {
    // POST to sigkill endpoint
    useMyFetch(`/api/completions/${systemId}/sigkill`, { method: 'POST' })
    // Mark locally as stopped for immediate UI feedback
    const msgIndex = messages.value.findIndex(m => m.id === sysMsg?.id)
    if (msgIndex !== -1) {
      const updatedMessage = { ...newMessages[msgIndex], status: 'stopped' }
      // Update all blocks to stopped
      updatedMessage.completion_blocks = updatedMessage.completion_blocks.map(block => ({
        ...block,
        status: block.status === 'in_progress' ? 'stopped' : block.status,
        completed_at: block.completed_at || new Date().toISOString()
      }))
      newMessages[msgIndex] = updatedMessage
      messages.value = newMessages
    }
  }
  isStreaming.value = false
}
```

**Backend Sigkill Handler (completion_service.py, lines 1058-1087):**
```python
async def update_completion_sigkill(self, db: AsyncSession, completion_id: str):
    completion = await db.execute(select(Completion).where(Completion.id == completion_id))
    completion = completion.scalars().first()

    if not completion:
        raise HTTPException(status_code=404, detail="Completion not found")
    
    completion.sigkill = datetime.now()
    completion.status = 'stopped'
    
    # Also update all in_progress completion blocks to stopped
    blocks_result = await db.execute(
        select(CompletionBlock).where(
            CompletionBlock.completion_id == completion_id,
            CompletionBlock.status == 'in_progress'
        )
    )
    blocks = blocks_result.scalars().all()
    
    for block in blocks:
        block.status = 'stopped'
        if not block.completed_at:
            block.completed_at = completion.sigkill
        db.add(block)
    
    await db.commit()
    await db.refresh(completion)

    return completion
```

### D. Background Polling While Disconnected

**When Started:**
- Page mounts and finds `in_progress` system message
- User is NOT actively streaming (isStreaming = false)

**What Gets Updated:**
- Completion status
- Completion blocks and their content
- Tool execution results
- Widget/step creations

**Why This Works:**
- All state is persisted in database
- AgentV2 continues executing server-side even if client disconnects
- Frontend polling catches up by fetching from database

---

## 6. Frontend Reconnection Logic

### SSE Streaming Handler (pages/reports/[id]/index.vue, lines 1574-1688)

**Error Handling During Streaming:**
```typescript
catch (err) {
  console.error('Streaming error:', err)
  const idx = messages.value.findIndex(m => m.id === sysId)
  if (idx !== -1) {
    let errorMessage = 'An error occurred during streaming.'
    
    if (err instanceof Error) {
      if (err.name === 'AbortError') {
        // Check if this was a user-initiated stop (sigkill) vs connection abort
        const sysMsg = messages.value[idx]
        if (sysMsg && sysMsg.system_completion_id) {
          // This was likely a user stop, mark as stopped without error
          messages.value[idx] = { ...messages.value[idx], status: 'stopped' }
          return  // Don't add error block for user stops
        } else {
          // Connection was aborted for other reasons
          errorMessage = 'Stream was cancelled.'
          messages.value[idx] = { ...messages.value[idx], status: 'stopped' }
        }
      } else if (err.message.includes('Stream HTTP error')) {
        errorMessage = `Connection error: ${err.message}`
        messages.value[idx] = { ...messages.value[idx], status: 'error' }
      } else {
        errorMessage = `Error: ${err.message}`
        messages.value[idx] = { ...messages.value[idx], status: 'error' }
      }
    } else {
      messages.value[idx] = { ...messages.value[idx], status: 'error' }
    }
    
    // Add error block if not already present
    if (!messages.value[idx].completion_blocks?.some(b => b.status === 'error')) {
      if (!messages.value[idx].completion_blocks) {
        messages.value[idx].completion_blocks = []
      }
      messages.value[idx].completion_blocks!.push({
        id: `error-${Date.now()}`,
        block_index: 999,
        status: 'error',
        content: errorMessage,
        title: 'Error',
        icon: '❌'
      })
    }
  }
} finally {
  isStreaming.value = false
  currentController = null
}
```

### Streaming Event Handlers (lines 736-1120)

**Block Upsert:**
```typescript
case 'block.upsert':
  // Add or update a completion block
  if (payload.block) {
    const block = payload.block
    if (!sysMessage.completion_blocks) {
      sysMessage.completion_blocks = []
    }
    
    // Find existing block or insert in-order by block_index
    const existingIndex = sysMessage.completion_blocks.findIndex(b => b.id === block.id)
    if (existingIndex >= 0) {
      // Update existing block in place
      Object.assign(sysMessage.completion_blocks[existingIndex], block)
    } else {
      // Insert new block in correct position
      let insertPos = sysMessage.completion_blocks.length
      for (let i = 0; i < sysMessage.completion_blocks.length; i++) {
        const bi = sysMessage.completion_blocks[i]
        if ((bi?.block_index ?? Number.MAX_SAFE_INTEGER) > (block?.block_index ?? Number.MAX_SAFE_INTEGER)) {
          insertPos = i
          break
        }
      }
      sysMessage.completion_blocks.splice(insertPos, 0, block)
    }
  }
  break
```

**Token Delta (for typing effect):**
```typescript
case 'block.delta.token':
  // Handle individual token streaming for real-time typing effect
  if (payload.block_id && payload.field && payload.token) {
    const idx = sysMessage.completion_blocks?.findIndex(b => b.id === payload.block_id) ?? -1
    if (idx >= 0 && sysMessage.completion_blocks) {
      const t = String(payload.token || '')
      const updated = { ...sysMessage.completion_blocks[idx] }
      if (payload.field === 'content') {
        updated.content = (updated.content || '') + t
      } else if (payload.field === 'reasoning') {
        updated.reasoning = (updated.reasoning || '') + t
        if (!updated.plan_decision) updated.plan_decision = {}
        updated.plan_decision.reasoning = (updated.plan_decision.reasoning || '') + t
      }
      sysMessage.completion_blocks.splice(idx, 1, updated)
    }
  }
  break
```

**Completion Finished:**
```typescript
case 'completion.finished':
  const completionStatus = (payload && typeof payload.status === 'string') ? payload.status : null
  if (completionStatus) {
    sysMessage.status = completionStatus as any
    if (completionStatus === 'error' && payload?.error?.message) {
      sysMessage.error_message = String(payload.error.message)
      // Ensure a single error block exists
      if (!sysMessage.completion_blocks?.some((b: any) => b.status === 'error')) {
        sysMessage.completion_blocks = sysMessage.completion_blocks || []
        sysMessage.completion_blocks.push({ 
          id: `error-${Date.now()}`, 
          block_index: 999, 
          status: 'error', 
          content: sysMessage.error_message 
        })
      }
    }
  }
  loadReport()  // Refresh report metadata
  break
```

---

## 7. "Last Event ID" and Cursor Mechanisms

### Current Approach: Database-Backed Cursor Pagination (NOT Event-Based Resume)

**Important:** There is **NO** SSE event ID resumption mechanism currently. However, there IS cursor pagination:

### Completion Cursor Pagination (completion_service.py, lines 444-619)

```python
async def get_completions_v2(
    self,
    db: AsyncSession,
    report_id: str,
    organization: Organization,
    current_user: User,
    limit: int = 10,
    before: str | None = None,
) -> CompletionsV2Response:
    """Assemble v2 completions response efficiently with batched queries.

    Returns the last `limit` completions (user+system) in reverse chronological order,
    then sorted ascending for UI render. If `before` is provided (ISO8601), fetches
    items strictly before that timestamp (cursor pagination).
    """
    # ... permission checks ...

    # 1) Fetch last N completions (user + system) with optional cursor
    completions_stmt = select(Completion).where(Completion.report_id == report_id)
    if before:
        try:
            from datetime import datetime as _dt
            before_dt = _dt.fromisoformat(before)
            completions_stmt = completions_stmt.where(Completion.created_at < before_dt)
        except Exception:
            pass
    # Order newest first, fetch one extra to determine has_more
    completions_stmt = completions_stmt.order_by(Completion.created_at.desc()).limit(limit + 1)
    
    # ... fetch and process blocks, tool executions, etc. ...

    return CompletionsV2Response(
        report_id=report_id,
        completions=v2_completions,
        total_completions=len(v2_completions),
        total_blocks=total_blocks,
        total_widgets_created=total_widgets,
        total_steps_created=total_steps,
        earliest_completion=earliest,
        latest_completion=latest,
        has_more=has_more,
        next_before=earliest,  # CURSOR: ISO datetime of oldest completion
    )
```

### Frontend Cursor Usage (pages/reports/[id]/index.vue, lines 1177-1242)

```typescript
// Pagination state
const pageLimit = 10
const hasMore = ref<boolean>(true)
const isLoadingMore = ref<boolean>(false)
const cursorBefore = ref<string | null>(null)

// Load previous page (older completions) and prepend while preserving scroll anchor
async function loadPreviousCompletions() {
  if (isLoadingMore.value || !hasMore.value) return
  const container = scrollContainer.value
  if (!container) return
  isLoadingMore.value = true
  const prevHeight = container.scrollHeight
  try {
    const qs = cursorBefore.value ? `&before=${encodeURIComponent(cursorBefore.value)}` : ''
    const { data } = await useMyFetch(`/reports/${report_id}/completions?limit=${pageLimit}${qs}`)
    const response = data.value as any
    const list: any[] = response?.completions || []
    
    // ... map completions ...
    
    // Dedupe by id and prepend
    const existingIds = new Set(messages.value.map(m => m.id))
    const toPrepend = newItems.filter(m => !existingIds.has(m.id))
    if (toPrepend.length > 0) {
      messages.value = [...toPrepend, ...messages.value]
      await nextTick()
      // Keep viewport anchored to previous items
      const newHeight = container.scrollHeight
      container.scrollTop = newHeight - prevHeight
    }
    hasMore.value = !!response?.has_more
    cursorBefore.value = response?.next_before || null  // UPDATE CURSOR
  } catch (e) {
    // keep hasMore as-is on error
  } finally {
    isLoadingMore.value = false
  }
}

// Triggered when user scrolls near top
function onScroll() {
  const container = scrollContainer.value
  if (!container) return
  // Infinite scroll trigger near top
  if (!isLoadingMore.value && hasMore.value) {
    const thresholdTop = 64
    if (container.scrollTop <= thresholdTop) {
      loadPreviousCompletions()
    }
  }
  // ... scroll position tracking ...
}
```

### AgentExecution Sequence Tracking (models/agent_execution.py)

```python
class AgentExecution(BaseSchema):
    # ...
    # STREAMING RESUME: Latest event sequence number
    latest_seq = Column(Integer, nullable=False, default=0)
```

**Usage in Agent:**
- Incremented as events are emitted
- Could be used for resumption (currently not implemented)
- Available for future SSE resume feature

---

## 8. Error Handling for Disconnections

### Network Disconnection Detection

**Frontend Streaming Loop (pages/reports/[id]/index.vue, lines 1596-1638):**
```typescript
while (true) {
  const { done, value } = await reader.read()
  if (done) {
    break  // Stream ended normally
  }
  
  // Check if stream was aborted
  if (currentController?.signal.aborted) {
    break  // User pressed stop
  }
  
  buffer += decoder.decode(value, { stream: true })
  // ... parse SSE events ...
}
```

### Error Classification

| Error Type | Detection | Recovery |
|------------|-----------|----------|
| **User Stop** | `AbortError` + `system_completion_id` | Mark as stopped (no error block) |
| **Network Abort** | `AbortError` without `system_completion_id` | Mark as stopped, could start polling |
| **HTTP Error** | `Stream HTTP error: {status}` | Mark as error, add error block |
| **Other Exception** | Catch-all | Mark as error, add error block |
| **Page Refresh** | SSE stream lost, polling starts | `startPollingInProgressCompletion()` |

### Resilience Strategy

```
┌─────────────────────────────────────────────────────────┐
│ Error Recovery Strategy                                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ During Streaming:                                       │
│  ├─ Network failure → Catch exception → Mark stopped   │
│  ├─ User clicks stop → AbortController → Send sigkill  │
│  └─ Stream ends normally → Parse [DONE] → Stop stream  │
│                                                         │
│ On Page Refresh (SSE breaks):                           │
│  └─ Mount detects in_progress → Start polling          │
│     ├─ Poll every 1.2s for up to 2 min                │
│     ├─ Fetch full state from DB                        │
│     └─ Display "Loading... showing recent progress"    │
│                                                         │
│ Persistent State:                                       │
│  ├─ Completion status stored (always recoverable)      │
│  ├─ All blocks persisted incrementally                 │
│  ├─ Tool results persisted to database                 │
│  └─ sigkill timestamp recorded on stop                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 9. Complete Data Flow Examples

### Example 1: Normal Streaming → Completion

```
1. User submits prompt
   └─→ Frontend: Creates temporary user + system messages
   └─→ Backend: create_completion_stream() starts

2. SSE Stream Opens
   └─→ completion.started event
   └─→ Frontend: Displays system message with in_progress status

3. Agent Executes (Background Task)
   └─→ AgentV2.main_execution()
   └─→ Emits: block.upsert, block.delta.token, tool.started, etc.

4. Stream Handlers Update UI
   └─→ Frontend: Updates completion_blocks in real-time
   └─→ User sees typing effect (block.delta.token)
   └─→ User sees tool execution progress

5. Completion Finished
   └─→ completion.finished event sent
   └─→ isStreaming = false
   └─→ Frontend loads full report metadata
   └─→ Blocks marked as success/error

6. Database State
   └─→ Completion.status = 'success'
   └─→ All CompletionBlocks persisted with status
   └─→ All ToolExecutions persisted
```

### Example 2: Page Refresh During Agent Execution

```
1. User on active streaming page
   └─→ SSE stream open, messages showing partial results

2. User refreshes page
   └─→ SSE stream breaks
   └─→ Frontend unmounts

3. Page remounts
   └─→ loadCompletions() fetches from DB
   └─→ Finds last system message with status='in_progress'
   └─→ Detects incomplete execution

4. Polling Starts
   └─→ startPollingInProgressCompletion()
   └─→ Every 1.2s: calls loadCompletions()
   └─→ UI shows "Loading… showing recent progress"

5. Agent Continues (Server-Side)
   └─→ AgentV2 task still running (asyncio.create_task)
   └─→ Events still being emitted to event_queue
   └─→ Database being updated incrementally

6. Poll Fetches Updates
   └─→ Completion.status still 'in_progress'
   └─→ New CompletionBlocks fetched
   └─→ Frontend updates completion_blocks array

7. Agent Finishes
   └─→ completion.status → 'success'
   └─→ All blocks complete
   └─→ Next poll detects completion
   └─→ stopPollingInProgressCompletion()
   └─→ Banner disappears
```

### Example 3: Network Disconnect During Streaming

```
1. User actively streaming
   └─→ Websocket connection drops
   └─→ Frontend SSE reader throws error

2. Catch Handler
   └─→ AbortError detected
   └─→ system_completion_id exists (we're mid-stream)
   └─→ marks message as 'stopped'

3. User Can:
   ├─ Manually refresh → Polling resumes
   ├─ Wait (implicit reconnection not implemented)
   └─ Press stop → Sends sigkill to backend

4. Server State
   └─→ Agent continues running if not interrupted
   └─→ All changes persisted to DB
   └─→ Polling will catch up eventually
```

### Example 4: User Clicks Stop

```
1. User clicks stop button
   └─→ abortStream() called

2. Frontend Actions
   ├─ currentController.abort() → breaks SSE reader
   ├─ Finds system_completion_id from message
   ├─ POST /api/completions/{id}/sigkill
   └─ Marks message.status = 'stopped'

3. Backend Actions
   └─→ update_completion_sigkill()
   ├─ Sets completion.sigkill = now()
   ├─ completion.status = 'stopped'
   └─ ALL CompletionBlocks with status='in_progress' → 'stopped'

4. Frontend Effects
   ├─ isStreaming = false
   ├─ No error block added (user-initiated)
   └─ "Generation stopped" message shown

5. Agent Loop
   └─→ Detects sigkill event (websocket_manager handler)
   └─→ Breaks main_execution loop
   └─→ Task completes gracefully
```

---

## 10. Summary: Recovery Mechanisms

| Scenario | Detection | Recovery | Duration | UI Feedback |
|----------|-----------|----------|----------|------------|
| **Active SSE Stream** | Events flowing normally | Continue streaming | Real-time | Live updates |
| **Page Refresh** | Mount finds `in_progress` | Start polling | Up to 2 min | "Loading… showing recent progress" |
| **Network Break** | Exception during stream read | Depends on user: polling or error | Up to 2 min polling | "Connection error" then offline |
| **User Stop** | User clicks stop button | Send sigkill + abort stream | Immediate | "Generation stopped" |
| **Backend Timeout** | No events for 1.2s polling window | Keeps polling until 2 min limit | Up to 2 min | Still shows banner |
| **Slow Network** | Delayed event arrival | Events still processed in order | As streamed | Slower typing effect |

---

## 11. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Vue)                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PromptBoxV2 (User Input)                                   │
│       ↓                                                     │
│  onSubmitCompletion()                                       │
│       ↓                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ STREAMING PHASE                                      │   │
│  │                                                      │   │
│  │ POST /completions + stream: true                    │   │
│  │      ↓                                               │   │
│  │ getReader() from response.body                       │   │
│  │      ↓                                               │   │
│  │ Parse SSE events:                                    │   │
│  │  - block.upsert                                      │   │
│  │  - block.delta.token (typing)                        │   │
│  │  - tool.started/progress/finished                    │   │
│  │  - completion.finished                               │   │
│  │      ↓                                               │   │
│  │ handleStreamingEvent() → Update messages[]           │   │
│  │      ↓                                               │   │
│  │ [DONE] marker → Stop streaming                       │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│       ↓                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ RECOVERY PHASE (if refresh or disconnect)           │   │
│  │                                                      │   │
│  │ onMounted():                                         │   │
│  │  - loadCompletions() [from DB via REST]             │   │
│  │  - Check: getLastInProgressSystem()                 │   │
│  │  - If found:                                         │   │
│  │    startPollingInProgressCompletion()               │   │
│  │       ↓                                              │   │
│  │    Every 1.2s:                                       │   │
│  │      - loadCompletions() [poll]                      │   │
│  │      - Check status changed to success/error         │   │
│  │      - If done: stopPollingInProgressCompletion()    │   │
│  │      - If timeout (2min): stop polling               │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  POST /api/reports/{id}/completions                         │
│       ↓                                                     │
│  create_completion_stream() [CompletionService]             │
│       ├─ Save Completion (status='in_progress')             │
│       ├─ Save system Completion                             │
│       ├─ Create CompletionEventQueue()                      │
│       ├─ asyncio.create_task(run_agent_with_streaming())    │
│       │   └─ AgentV2.main_execution()                       │
│       │      ├─ Loop through plan decisions                 │
│       │      ├─ Execute tools                               │
│       │      ├─ Emit SSEEvent to event_queue                │
│       │      │   (block.upsert, block.delta.token, etc)     │
│       │      ├─ Update DB incrementally                     │
│       │      └─ Completion.status → 'success'/'error'       │
│       │                                                      │
│       └─ Return StreamingResponse                           │
│          ├─ Yield SSE formatted events from queue           │
│          ├─ Format: "event: X\ndata: {...}\n\n"             │
│          └─ Final: "data: [DONE]\n\n"                       │
│                                                             │
│  GET /api/reports/{id}/completions [polling endpoint]       │
│       ↓                                                     │
│  get_completions_v2() [CompletionService]                   │
│       ├─ Fetch Completions + CompletionBlocks from DB       │
│       ├─ Optional cursor pagination (before: ISO datetime)  │
│       └─ Return CompletionsV2Response with has_more         │
│                                                             │
│  POST /api/completions/{id}/sigkill [stop endpoint]         │
│       ↓                                                     │
│  update_completion_sigkill() [CompletionService]            │
│       ├─ Set completion.sigkill = now()                     │
│       ├─ completion.status = 'stopped'                      │
│       ├─ ALL in_progress blocks → 'stopped'                 │
│       └─ Return updated completion                          │
│                                                             │
│  DATABASE (SQLAlchemy + PostgreSQL)                         │
│  ├─ Completion (status, sigkill, completion JSON)           │
│  ├─ CompletionBlock (status, content, reasoning)            │
│  ├─ AgentExecution (status, latest_seq)                     │
│  ├─ ToolExecution (result_json, status)                     │
│  └─ Event hooks broadcast updates via WebSocket             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. Key Takeaways

### Design Principles

1. **Database-First State Management**
   - All critical state lives in database
   - SSE is ephemeral transport, not state store
   - Recovery always possible from DB

2. **Stateless Polling Recovery**
   - No complex SSE resumption logic
   - Simple HTTP polling for refresh recovery
   - Scales horizontally

3. **Graceful Degradation**
   - Real-time streaming when connected
   - Polling fallback when disconnected
   - User always sees recent progress

4. **Clear Status Lifecycle**
   - Completion → in_progress → success/error/stopped
   - Blocks inherit status from execution
   - sigkill timestamp tracks user stops

### Limitations & Gaps

1. **No SSE Resumption**
   - AgentExecution.latest_seq available but not used
   - Could implement event ID tracking for future optimization

2. **2-Minute Polling Timeout**
   - Long-running agents will stop showing updates after 2 minutes
   - User can refresh to restart polling

3. **No Automatic Reconnection**
   - User must refresh to resume after network break
   - Could implement exponential backoff retry

4. **Polling Latency**
   - Up to 1.2 seconds between polls
   - Trade-off for simplicity and server load

### Production Readiness

- State persistence: ✅ Robust
- Disconnection recovery: ✅ Working (polling)
- Error handling: ✅ Comprehensive
- User stop capability: ✅ Implemented (sigkill)
- Long-running agents: ⚠️ Limited (2min polling)
- Network resilience: ⚠️ Manual refresh required

