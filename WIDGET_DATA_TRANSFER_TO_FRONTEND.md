# Widget Data Transfer from Backend to Frontend Chart

**Architecture**: Backend (FastAPI) → Frontend (Nuxt 3 Vue) → ECharts Rendering

This document explains the complete data flow from backend widget creation to frontend chart visualization.

---

## Overview: The Complete Data Flow

```
Backend Agent        Backend API           Frontend API         Frontend Components     ECharts
    ↓                    ↓                      ↓                        ↓                   ↓
1. Create Widget    → 2. Store in DB    → 3. Fetch via HTTP  → 4. Transform Data  → 5. Render Chart
2. Generate Code       WebSocket Broadcast    REST API             to Options           Canvas
3. Execute Code        Update Events          Polling              ECharts Config       Interactive
4. Save Data Model                            SSE Streaming                             Visualization
5. Save DataFrame
```

---

## Phase 1: Backend - Widget & Data Creation

**Location**: `backend/app/ai/agent.py:298-366`

### 1.1 Widget Creation

```python
# Create widget entity
widget = await self.project_manager.create_widget(
    self.db,
    self.report,
    action['details']['title']  # "Revenue by Region"
)
```

**Database Record**:
```python
Widget(
    id="uuid-widget-123",
    title="Revenue by Region",
    report_id="uuid-report-456",
    x=None,  # Position set by dashboard designer later
    y=None,
    width=None,
    height=None,
    created_at="2025-01-15T10:30:00Z"
)
```

### 1.2 Step Creation with Data Model

```python
# Create step linked to widget
step = await self.project_manager.create_step(
    self.db,
    action['details']['title'],
    widget,
    "table"  # Initial type
)

# Save data model to step
step.data_model = action['details']['data_model']
self.db.add(step)
await self.db.commit()
```

**Data Model Structure**:
```json
{
  "type": "bar_chart",
  "columns": [
    {
      "generated_column_name": "region",
      "source": "sales.region",
      "description": "Sales region identifier",
      "source_data_source_id": "uuid-ds-789"
    },
    {
      "generated_column_name": "revenue",
      "source": "SUM(sales.amount)",
      "description": "Total revenue",
      "source_data_source_id": "uuid-ds-789"
    }
  ],
  "series": [
    {
      "name": "Revenue",
      "key": "region",
      "value": "revenue"
    }
  ],
  "group_by": ["region"]
}
```

### 1.3 Code Generation & Execution

**Location**: `backend/app/ai/agents/coder/coder.py:113-250`

```python
# Coder generates Python code from data model
code = await self.coder.data_model_to_code(
    data_model=data_model,
    schemas=schemas,
    ...
)
```

**Generated Code Example**:
```python
import pandas as pd

def generate_df(db_clients, excel_files):
    # Access the database client
    db = db_clients.get('postgres_main')

    # Execute SQL query
    query = """
        SELECT
            region,
            SUM(amount) as revenue
        FROM sales
        GROUP BY region
        ORDER BY revenue DESC
    """

    df = pd.read_sql(query, db.get_connection())
    return df
```

**Code Execution**: `backend/app/ai/code_execution/code_execution.py`

```python
# Execute the generated code
df, final_code, _ = await self.code_execution_manager.generate_and_execute_with_retries(...)

# df is now a pandas DataFrame:
#     region   revenue
# 0   North    150000
# 1   South    180000
# 2   East     210000
# 3   West     120000
```

### 1.4 Data Formatting & Storage

```python
# Convert DataFrame to widget-compatible JSON
widget_data = self.code_execution_manager.format_df_for_widget(df)

# Save to step
await self.project_manager.update_step_with_data(self.db, step, widget_data)
```

**Stored Data Format** (`step.data`):
```json
{
  "columns": [
    { "field": "region", "headerName": "Region" },
    { "field": "revenue", "headerName": "Revenue" }
  ],
  "rows": [
    { "region": "North", "revenue": 150000 },
    { "region": "South", "revenue": 180000 },
    { "region": "East", "revenue": 210000 },
    { "region": "West", "revenue": 120000 }
  ],
  "info": {
    "row_count": 4,
    "column_count": 2
  }
}
```

**Complete Step Record**:
```python
Step(
    id="uuid-step-111",
    widget_id="uuid-widget-123",
    title="Revenue by Region",
    type="table",
    data_model={...},  # From step 1.2
    data={...},        # From above
    code="import pandas as pd\n...",
    status="success",
    created_at="2025-01-15T10:30:15Z"
)
```

---

## Phase 2: Backend - Real-time Updates

### 2.1 WebSocket Broadcast

**Location**: `backend/app/websocket_manager.py`

When a widget or step is saved, SQLAlchemy event listeners trigger WebSocket broadcasts:

```python
# WebSocket manager automatically broadcasts
websocket_manager.broadcast({
    "event": "update_widget",
    "widget_id": "uuid-widget-123",
    "report_id": "uuid-report-456"
})

websocket_manager.broadcast({
    "event": "update_step",
    "step_id": "uuid-step-111",
    "widget_id": "uuid-widget-123"
})
```

### 2.2 SSE Streaming (During Creation)

**Location**: `backend/app/ai/agent.py:183-226`

While the agent is running, it streams progress via Server-Sent Events:

```
event: block.upsert
data: {"block": {"id": "block-1", "content": "Creating bar chart...", "status": "in_progress"}}

event: tool.progress
data: {"tool_name": "create_widget", "payload": {"stage": "data_model_type_determined", "data_model_type": "bar_chart"}}

event: tool.progress
data: {"tool_name": "create_widget", "payload": {"stage": "column_added", "column": {"generated_column_name": "region", ...}}}

event: tool.completed
data: {"block_id": "block-1", "status": "completed"}
```

---

## Phase 3: Frontend - Data Fetching

### 3.1 Initial Page Load

**Location**: `frontend/pages/reports/[id]/index.vue:1739-1751`

```typescript
onMounted(async () => {
    await Promise.all([
        loadReport(),          // Fetch report metadata
        loadVisualizations(),  // Fetch all visualizations
        loadCompletions(),     // Fetch chat messages
        loadActiveLayoutHasBlocks()  // Check if dashboard exists
    ])
})
```

### 3.2 Load Visualizations

**Location**: `frontend/pages/reports/[id]/index.vue:1283-1298`

```typescript
async function loadVisualizations() {
    // Fetch all queries for this report
    const { data } = await useMyFetch(`/api/queries?report_id=${report_id}`)
    const queries = data.value

    // Extract visualizations from queries
    const list = []
    for (const q of queries) {
        for (const v of (q?.visualizations || [])) {
            if (v && v.id) list.push(v)
        }
    }

    visualizations.value = list
}
```

**Visualization Object**:
```typescript
{
    id: "uuid-viz-123",
    query_id: "uuid-query-456",
    title: "Revenue by Region",
    status: "published",
    view: {
        type: "bar_chart",
        titleVisible: true,
        legendVisible: false
    }
}
```

### 3.3 Dashboard Component Fetches Steps

**Location**: `frontend/components/DashboardComponent.vue:267-279`

```typescript
onMounted(async () => {
    initializeMainGrid()
    await fetchActiveLayout()    // Get dashboard layout
    await loadQueriesForReport() // Load queries
    await fetchAllWidgets()      // Load widgets with steps
    loadWidgetsIntoGrid(grid.value, allWidgets.value)
})
```

### 3.4 Fetch Active Layout

```typescript
async function fetchActiveLayout() {
    const { data } = await useMyFetch(`/api/reports/${report_id}/layouts`)
    const layouts = data.value
    const active = layouts.find(l => l.is_active)

    if (active) {
        activeLayout.value = active
        layoutBlocks.value = active.blocks || []
    }
}
```

**Layout Blocks Structure**:
```json
{
  "id": "uuid-layout-001",
  "is_active": true,
  "blocks": [
    {
      "type": "visualization",
      "visualization_id": "uuid-viz-123",
      "x": 0,
      "y": 0,
      "width": 6,
      "height": 4,
      "view_overrides": {
        "legendVisible": true
      }
    }
  ]
}
```

### 3.5 Apply Layout & Fetch Steps

**Location**: `frontend/components/DashboardComponent.vue:450-545`

```typescript
async function applyLayoutToLocalState() {
    const blocks = layoutBlocks.value
    const nextDisplayed = []

    for (const b of blocks) {
        if (b.type === 'visualization') {
            const viz = vizById.value[b.visualization_id]
            const qid = viz.query_id

            // Fetch default step for this query
            let step = await ensureDefaultStepForQuery(qid)

            nextDisplayed.push({
                id: viz.id,
                x: b.x,
                y: b.y,
                width: b.width,
                height: b.height,
                title: viz.title,
                last_step: step,  // ← Step with data + data_model
                view: viz.view
            })
        }
    }

    displayedWidgets.value = nextDisplayed
}
```

### 3.6 Fetch Default Step

**Location**: `frontend/components/DashboardComponent.vue:413-448`

```typescript
async function ensureDefaultStepForQuery(queryId: string) {
    // Fetch the default step for this query
    const { data } = await useMyFetch(`/api/queries/${queryId}/default_step`)
    const step = data.value.step

    // Cache the step
    stepCache.value[step.id] = step

    return step
}
```

**API Response** (`GET /api/queries/{query_id}/default_step`):
```json
{
  "step": {
    "id": "uuid-step-111",
    "query_id": "uuid-query-456",
    "title": "Revenue by Region",
    "type": "table",
    "data_model": {
      "type": "bar_chart",
      "columns": [...],
      "series": [...]
    },
    "data": {
      "columns": [...],
      "rows": [
        { "region": "North", "revenue": 150000 },
        { "region": "South", "revenue": 180000 },
        { "region": "East", "revenue": 210000 },
        { "region": "West", "revenue": 120000 }
      ]
    },
    "code": "import pandas as pd\n...",
    "status": "success"
  }
}
```

---

## Phase 4: Frontend - Component Rendering

### 4.1 Widget Frame Component

**Location**: `frontend/components/dashboard/regular/RegularWidgetView.vue:13-24`

```vue
<template>
  <div class="flex-grow overflow-auto p-2 min-h-0">
    <component
      :is="resolvedComp"
      :widget="widget"
      :data="widget.last_step?.data"         <!-- ← Data from backend -->
      :data_model="widget.last_step?.data_model"  <!-- ← Data model from backend -->
      :step="widget.last_step"
      :view="finalView"
      :reportThemeName="themeName"
    />
  </div>
</template>
```

**Props Passed to Chart**:
```typescript
{
    widget: {
        id: "uuid-viz-123",
        title: "Revenue by Region",
        last_step: {
            data: { columns: [...], rows: [...] },
            data_model: { type: "bar_chart", ... }
        }
    },
    data: {
        columns: [
            { field: "region", headerName: "Region" },
            { field: "revenue", headerName: "Revenue" }
        ],
        rows: [
            { region: "North", revenue: 150000 },
            { region: "South", revenue: 180000 },
            { region: "East", revenue: 210000 },
            { region: "West", revenue: 120000 }
        ]
    },
    data_model: {
        type: "bar_chart",
        series: [
            { name: "Revenue", key: "region", value: "revenue" }
        ]
    },
    view: {
        type: "bar_chart",
        titleVisible: true,
        legendVisible: true
    }
}
```

---

## Phase 5: Frontend - ECharts Transformation

### 5.1 ECharts Visual Component

**Location**: `frontend/components/dashboard/charts/EChartsVisual.vue:430-517`

```typescript
function buildOptions() {
    // 1. Get base options (title, grid, legend)
    const base = getBaseOptions()

    // 2. Normalize data rows (lowercase keys)
    const rows = normalizeRows(props.data?.rows)

    // 3. Get chart type
    const t = normalizeType(props.data_model?.type)

    // 4. Build chart-specific options
    let specific = {}
    if (t === 'bar_chart') {
        specific = buildCartesianOptions(rows, props.data_model)
    } else if (t === 'pie_chart') {
        specific = buildPieOptions(rows, props.data_model)
    }
    // ... other chart types

    // 5. Merge base + specific
    const merged = { ...base, ...specific }

    // 6. Apply theme colors
    applyThemeColors(merged, t, props.data_model)

    // 7. Set chart options
    chartOptions.value = merged
}
```

### 5.2 Data Normalization

```typescript
function normalizeRows(rows: any[]): any[] {
    return rows.map(r => {
        const o = {}
        Object.keys(r).forEach(k => (o[k.toLowerCase()] = r[k]))
        return o
    })
}
// Input:  [{ Region: "North", Revenue: 150000 }]
// Output: [{ region: "North", revenue: 150000 }]
```

### 5.3 Build Cartesian Chart Options (Bar/Line/Area)

**Location**: `frontend/components/dashboard/charts/EChartsVisual.vue:143-217`

```typescript
function buildCartesianOptions(rows, dm) {
    // 1. Get category key (x-axis)
    const categoryKey = dm?.series?.[0]?.key?.toLowerCase()  // "region"

    // 2. Extract unique categories
    const categories = Array.from(new Set(rows.map(r => r[categoryKey])))
    // ["North", "South", "East", "West"]

    // 3. Build series data
    const series = dm.series.map(s => {
        const valueKey = s.value.toLowerCase()  // "revenue"
        const data = categories.map(cat => {
            const row = rows.find(r => r[categoryKey] === cat)
            return row ? Number(row[valueKey]) : null
        })
        // [150000, 180000, 210000, 120000]

        return {
            name: s.name,  // "Revenue"
            type: 'bar',
            data: data
        }
    })

    // 4. Return ECharts configuration
    return {
        tooltip: { trigger: 'axis' },
        xAxis: {
            type: 'category',
            data: categories,  // ["North", "South", "East", "West"]
            name: dm.series[0]?.key || 'Categories'
        },
        yAxis: {
            type: 'value',
            name: 'Values'
        },
        series: series  // [{ name: "Revenue", type: "bar", data: [150000, ...] }]
    }
}
```

### 5.4 Final ECharts Options

**Result**:
```javascript
{
    title: {
        text: "Revenue by Region",
        left: "center",
        top: 5
    },
    grid: {
        containLabel: true,
        left: 0,
        right: 0,
        bottom: 2,
        top: 40
    },
    legend: {
        show: true,
        left: "center",
        bottom: 0
    },
    tooltip: {
        trigger: "axis"
    },
    xAxis: {
        type: "category",
        data: ["North", "South", "East", "West"],
        name: "region",
        axisLabel: { interval: 0, rotate: 0 }
    },
    yAxis: {
        type: "value",
        name: "Values"
    },
    series: [
        {
            name: "Revenue",
            type: "bar",
            data: [150000, 180000, 210000, 120000],
            itemStyle: {
                color: "#3b82f6"  // Applied from theme
            }
        }
    ],
    color: ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"]  // Theme palette
}
```

### 5.5 Render Chart

**Location**: `frontend/components/dashboard/charts/EChartsVisual.vue:3-4`

```vue
<template>
  <div class="h-full w-full">
    <VChart
      :key="chartKey"
      class="chart"
      :option="chartOptions"  <!-- ← ECharts options from above -->
      autoresize
    />
  </div>
</template>
```

**VChart** is the Vue-ECharts component that:
1. Takes the options object
2. Creates a canvas element
3. Initializes ECharts instance
4. Renders the interactive chart

---

## Phase 6: Real-Time Updates

### 6.1 Polling Recovery (After Page Refresh)

**Location**: `frontend/pages/reports/[id]/index.vue:1707-1737`

If user refreshes the page while a completion is in progress:

```typescript
// Check for in-progress system message
if (getLastInProgressSystem()) {
    startPollingInProgressCompletion()
}

async function startPollingInProgressCompletion() {
    const tick = async () => {
        await loadCompletions()  // Re-fetch completions
        autoScrollIfNearBottom()

        // Check if still in progress
        const still = getLastInProgressSystem()
        if (!still) {
            stopPollingInProgressCompletion()
            return
        }

        // Poll every 1.2 seconds for up to 2 minutes
        pollHandle = window.setTimeout(tick, 1200)
    }

    pollHandle = window.setTimeout(tick, 1200)
}
```

### 6.2 SSE Streaming (Live Updates)

**Location**: `frontend/pages/reports/[id]/index.vue:877-896`

During active streaming, progressive updates are received:

```typescript
async function handleStreamingEvent(event, payload, idx) {
    switch (event) {
        case 'block.delta.artifact':
            // Update data model as it's being generated
            if (payload.change?.fields?.data_model) {
                const block = sysMessage.completion_blocks[...]
                block.tool_execution.result_json.data_model = {
                    ...block.tool_execution.result_json.data_model,
                    ...payload.change.fields.data_model
                }
            }
            break

        case 'tool.progress':
            // Show progress stage
            if (payload.tool_name === 'create_widget') {
                if (payload.payload.stage === 'column_added') {
                    // Add column to preview
                    rj.data_model.columns.push(payload.payload.column)
                }
            }
            break
    }
}
```

### 6.3 WebSocket Entity Updates

While not shown in the report page directly, the `backend/app/websocket_manager.py` broadcasts:

```python
# When widget is updated via dashboard drag/resize
websocket_manager.broadcast({
    "event": "update_widget",
    "widget_id": "uuid-widget-123",
    "x": 6,
    "y": 0,
    "width": 8,
    "height": 5
})
```

This allows **collaborative editing** - if two users are viewing the same report, both see changes in real-time.

---

## Data Transformation Summary

### Backend Data

```json
{
  "step": {
    "data": {
      "rows": [
        { "region": "North", "revenue": 150000 },
        { "region": "South", "revenue": 180000 }
      ]
    },
    "data_model": {
      "type": "bar_chart",
      "series": [
        { "name": "Revenue", "key": "region", "value": "revenue" }
      ]
    }
  }
}
```

### Frontend Transformation

```javascript
// 1. Normalize keys
rows = [
    { region: "North", revenue: 150000 },
    { region: "South", revenue: 180000 }
]

// 2. Extract categories
categories = ["North", "South"]

// 3. Extract series values
data = [150000, 180000]

// 4. Build ECharts series
series = [{
    name: "Revenue",
    type: "bar",
    data: [150000, 180000]
}]
```

### ECharts Final Options

```javascript
{
    xAxis: { type: "category", data: ["North", "South"] },
    yAxis: { type: "value" },
    series: [{ name: "Revenue", type: "bar", data: [150000, 180000] }]
}
```

---

## Chart Type Mappings

| Data Model Type | ECharts Type | Builder Function | Series Structure |
|-----------------|--------------|------------------|------------------|
| `bar_chart` | `bar` | `buildCartesianOptions()` | `{ key, value }` |
| `line_chart` | `line` | `buildCartesianOptions()` | `{ key, value }` |
| `area_chart` | `line` + `areaStyle` | `buildCartesianOptions()` | `{ key, value }` |
| `pie_chart` | `pie` | `buildPieOptions()` | `{ key, value }` |
| `scatter_plot` | `scatter` | `buildScatterOptions()` | `{ x, y }` |
| `heatmap` | `heatmap` | `buildHeatmapOptions()` | `{ x, y, value }` |
| `candlestick` | `candlestick` | `buildCandlestickOptions()` | `{ key, open, close, low, high }` |
| `treemap` | `treemap` | `buildTreemapOptions()` | `{ id, parentId, value }` |
| `radar_chart` | `radar` | `buildRadarOptions()` | `{ dimensions, name }` |

---

## API Endpoints Used

### Backend Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/reports/{id}` | GET | Fetch report metadata |
| `/api/queries?report_id={id}` | GET | Fetch all queries + visualizations |
| `/api/queries/{id}/default_step` | GET | Fetch default step with data + data_model |
| `/api/reports/{id}/layouts` | GET | Fetch dashboard layouts |
| `/api/completions/stream` | POST | SSE stream for agent execution |
| `/ws` | WebSocket | Real-time entity updates |

### Data Flow Diagram

```
User submits prompt
       ↓
SSE Stream starts (tool.progress events)
       ↓
Backend Agent creates Widget
       ↓
Backend Agent creates Step with data_model
       ↓
Backend Agent generates Python code
       ↓
Backend Agent executes code → DataFrame
       ↓
Backend Agent saves step.data (rows/columns)
       ↓
WebSocket broadcasts update_widget, update_step
       ↓
SSE Stream emits tool.completed
       ↓
Frontend: GET /api/queries/{id}/default_step
       ↓
Frontend receives { step: { data, data_model } }
       ↓
Frontend passes data + data_model to EChartsVisual
       ↓
EChartsVisual.buildOptions() transforms to ECharts config
       ↓
VChart component renders canvas with ECharts
       ↓
User sees interactive bar chart!
```

---

## Key Takeaways

1. **Data Lives in Step**: All chart data and configuration is stored in the `Step` model
   - `step.data`: The actual DataFrame rows/columns (JSON)
   - `step.data_model`: The visualization configuration (chart type, series, columns)
   - `step.code`: The Python code that generated the data

2. **Widget is a Container**: The `Widget` model only holds metadata
   - Title, position (x, y, width, height)
   - Links to steps via `widget_id`
   - Multiple steps per widget (versioning)

3. **Data Model Drives Rendering**: The `data_model` tells the frontend HOW to visualize the data
   - Chart type (bar, pie, line, etc.)
   - Series configuration (which columns map to x/y/value)
   - Grouping and aggregation hints

4. **Three Data Transfer Paths**:
   - **SSE Streaming**: Real-time progress during creation
   - **REST API**: Fetch complete widget data on load
   - **WebSocket**: Collaborative updates (position, title changes)

5. **Frontend Transformation**: Raw data → Normalized data → ECharts options
   - Normalizes keys to lowercase
   - Extracts categories and series values
   - Applies theme colors and styling
   - Generates ECharts configuration object

6. **Recovery Mechanism**: If user refreshes during creation, polling continues fetching until complete

The entire system is designed for **progressive enhancement** - users see partial results as they stream in, then full interactivity once complete!
