# Frontend Data Normalization for ECharts

**Location**: `frontend/components/dashboard/charts/EChartsVisual.vue`

This document shows the complete data normalization pipeline that transforms backend DataFrame data into ECharts-ready format.

---

## Overview: The Normalization Pipeline

```
Backend Data          Normalize Rows       Extract Categories    Map Series Data    ECharts Options
(Mixed case keys) →   (Lowercase keys) →   (Unique values)   →   (Aligned arrays) → (Chart config)
```

---

## Step 1: Normalize Row Keys to Lowercase

**Location**: `EChartsVisual.vue:85-92`

### The normalizeRows Function

```typescript
function normalizeRows(rows: any[] | undefined): any[] {
  // Return empty array if rows is not an array
  if (!Array.isArray(rows)) return []

  // Map each row to a new object with lowercase keys
  return rows.map(r => {
    const o: any = {}
    Object.keys(r).forEach(k => (o[k.toLowerCase()] = r[k]))
    return o
  })
}
```

### Why Normalize?

**Problem**: Backend data keys might have inconsistent casing
- SQL column names: `REGION`, `Region`, `region`
- Python DataFrame: `Region`, `Revenue`
- User-defined: Any casing

**Solution**: Convert all keys to lowercase for predictable access

### Example Transformation

**Input (from backend)**:
```javascript
[
  { Region: "North", Revenue: 150000, Year: 2024 },
  { Region: "South", Revenue: 180000, Year: 2024 },
  { Region: "East", Revenue: 210000, Year: 2024 }
]
```

**After normalizeRows()**:
```javascript
[
  { region: "north", revenue: 150000, year: 2024 },
  { region: "south", revenue: 180000, year: 2024 },
  { region: "east", revenue: 210000, year: 2024 }
]
```

**Code Flow**:
```javascript
// Input row
{ Region: "North", Revenue: 150000 }

// Object.keys(r) => ["Region", "Revenue"]

// forEach iteration:
// k = "Region"  → o["region"] = "North"
// k = "Revenue" → o["revenue"] = 150000

// Output row
{ region: "North", revenue: 150000 }
```

**Note**: Values are NOT lowercased, only keys!

---

## Step 2: Build Cartesian Chart Options (Bar/Line/Area)

**Location**: `EChartsVisual.vue:143-217`

### Complete buildCartesianOptions Function

```typescript
function buildCartesianOptions(rows: any[], dm: any): EChartsOption {
  // 1. Determine chart type (bar or line)
  const t = normalizeType((props.view as any)?.type || dm?.type)
  const variant = props.view?.variant || (t === 'area_chart' ? 'area' : undefined)
  const chartType = t === 'line_chart' || variant === 'area' ? 'line' : 'bar'

  // 2. Get category key (x-axis) from data model
  const categoryKey = dm?.series?.[0]?.key?.toLowerCase()
  if (!categoryKey) return {}  // Cannot build chart without category

  // 3. Extract unique categories from all rows
  const categories = Array.from(
    new Set(rows.map((r: any) => String(r[categoryKey] ?? '')))
  )

  // 4. Build series data for each series in data model
  const series = (dm?.series || [])
    .map((s: any) => {
      const valueKey = s?.value?.toLowerCase()
      if (!valueKey) return null

      // Map each category to its corresponding value
      const data = categories.map(cat => {
        const row = rows.find((r: any) => String(r[categoryKey] ?? '') === cat)
        const v = row ? Number(row[valueKey]) : null
        return Number.isNaN(v as number) ? null : v
      })

      const base: any = { name: s.name, type: chartType, data }
      if (chartType === 'line' && variant === 'area') base.areaStyle = {}
      if (chartType === 'line' && props.view?.variant === 'smooth') base.smooth = true
      return base
    })
    .filter(Boolean)  // Remove null entries

  // 5. Build axis configuration
  const axisColors = { ...(tokens.value?.axis || {}), ...((props.view?.style as any)?.axis || {}) }
  const xVisible = props.view?.xAxisVisible ?? true
  const yVisible = props.view?.yAxisVisible ?? true

  // 6. Return ECharts options
  return {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: categories,  // Array of category values
      name: dm?.series?.[0]?.key || 'Categories',
      show: xVisible,
      axisLabel: { color: axisColors.xLabelColor },
      axisLine: { lineStyle: { color: axisColors.xLineColor } }
    },
    yAxis: {
      type: 'value',
      name: 'Values',
      show: yVisible,
      axisLabel: { color: axisColors.yLabelColor },
      axisLine: { lineStyle: { color: axisColors.yLineColor } }
    },
    legend: { show: props.view?.legendVisible ?? false },
    series: series
  }
}
```

### Step-by-Step Example

#### Input Data

**Normalized Rows**:
```javascript
[
  { region: "North", revenue: 150000, cost: 100000 },
  { region: "South", revenue: 180000, cost: 120000 },
  { region: "East", revenue: 210000, cost: 140000 },
  { region: "West", revenue: 120000, cost: 80000 }
]
```

**Data Model**:
```javascript
{
  type: "bar_chart",
  series: [
    { name: "Revenue", key: "region", value: "revenue" },
    { name: "Cost", key: "region", value: "cost" }
  ]
}
```

#### Step 2.1: Get Category Key

```javascript
const categoryKey = dm.series[0].key.toLowerCase()
// categoryKey = "region"
```

#### Step 2.2: Extract Unique Categories

```javascript
// Map each row to its category value
rows.map((r: any) => String(r[categoryKey] ?? ''))
// ["North", "South", "East", "West"]

// Get unique values using Set
const categories = Array.from(new Set([...]))
// ["North", "South", "East", "West"]
```

**Why unique?** Prevents duplicate categories if data has multiple rows per category.

#### Step 2.3: Build First Series (Revenue)

```javascript
const s = { name: "Revenue", key: "region", value: "revenue" }
const valueKey = s.value.toLowerCase()  // "revenue"

// Map each category to its value
const data = categories.map(cat => {
  // Find row where region === cat
  const row = rows.find((r: any) => String(r[categoryKey] ?? '') === cat)
  // row for "North" = { region: "North", revenue: 150000, cost: 100000 }

  // Extract value
  const v = row ? Number(row[valueKey]) : null
  // v = 150000

  // Return value (or null if NaN)
  return Number.isNaN(v) ? null : v
})

// Result:
data = [150000, 180000, 210000, 120000]
//       North   South   East    West
```

**Alignment**: Data array MUST align with categories array by index!

#### Step 2.4: Build Second Series (Cost)

```javascript
const s = { name: "Cost", key: "region", value: "cost" }
const valueKey = s.value.toLowerCase()  // "cost"

// Same mapping process
const data = categories.map(cat => {
  const row = rows.find((r: any) => String(r[categoryKey] ?? '') === cat)
  const v = row ? Number(row[valueKey]) : null
  return Number.isNaN(v) ? null : v
})

// Result:
data = [100000, 120000, 140000, 80000]
//       North   South   East    West
```

#### Step 2.5: Final Series Array

```javascript
series = [
  {
    name: "Revenue",
    type: "bar",
    data: [150000, 180000, 210000, 120000]
  },
  {
    name: "Cost",
    type: "bar",
    data: [100000, 120000, 140000, 80000]
  }
]
```

#### Final ECharts Options

```javascript
{
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: ["North", "South", "East", "West"],
    name: "region"
  },
  yAxis: {
    type: 'value',
    name: 'Values'
  },
  series: [
    {
      name: "Revenue",
      type: "bar",
      data: [150000, 180000, 210000, 120000]
    },
    {
      name: "Cost",
      type: "bar",
      data: [100000, 120000, 140000, 80000]
    }
  ]
}
```

**Visual Result**:
```
          Revenue by Region
     ┌────────────────────────┐
250K │                        │
     │           ┌────┐       │
200K │     ┌────┐│████│       │
     │     │████││████│       │
150K │┌────┤████││████│       │
     ││████│████││████│ ┌────┐│
100K ││████│████││████│ │████││
     ││████│████││████│ │████││
 50K ││████│████││████│ │████││
     │└────┴────┴────┴─┴────┘│
       North South East  West

     ■ Revenue  ■ Cost
```

---

## Step 3: Build Pie Chart Options

**Location**: `EChartsVisual.vue:131-141`

### buildPieOptions Function

```typescript
function buildPieOptions(rows: any[], dm: any): EChartsOption {
  const cfg = dm?.series?.[0] || {}
  if (!cfg?.key || !cfg?.value) return {}

  // Map rows to pie data format
  const data = rows
    .map((r: any) => ({
      name: r[cfg.key.toLowerCase()],
      value: Number(r[cfg.value.toLowerCase()])
    }))
    .filter((d: any) => d.name != null && !Number.isNaN(d.value))

  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      name: cfg.name,
      type: 'pie',
      radius: ['40%', '70%'],  // Donut chart
      center: ['50%', '60%'],
      data: data
    }]
  }
}
```

### Pie Chart Example

**Normalized Rows**:
```javascript
[
  { category: "Product A", sales: 45000 },
  { category: "Product B", sales: 30000 },
  { category: "Product C", sales: 25000 }
]
```

**Data Model**:
```javascript
{
  type: "pie_chart",
  series: [
    { name: "Sales", key: "category", value: "sales" }
  ]
}
```

**Transformation**:
```javascript
// cfg.key = "category", cfg.value = "sales"

// Map each row
rows.map((r: any) => ({
  name: r["category"],        // "Product A"
  value: Number(r["sales"])   // 45000
}))

// Result
data = [
  { name: "Product A", value: 45000 },
  { name: "Product B", value: 30000 },
  { name: "Product C", value: 25000 }
]
```

**ECharts Options**:
```javascript
{
  series: [{
    type: 'pie',
    data: [
      { name: "Product A", value: 45000 },
      { name: "Product B", value: 30000 },
      { name: "Product C", value: 25000 }
    ]
  }]
}
```

---

## Step 4: Main buildOptions Orchestration

**Location**: `EChartsVisual.vue:430-517`

### Complete Flow

```typescript
function buildOptions() {
  isLoading.value = true
  chartOptions.value = {}

  // 1. Get data model (from props or inferred)
  let dm = props.data_model || {}

  // 2. NORMALIZE ROWS - Convert all keys to lowercase
  const rows = normalizeRows(props.data?.rows)

  // 3. Check if we have data
  if (!dm || !rows.length) {
    isLoading.value = false
    return
  }

  // 4. Get normalized chart type
  const t = normalizeType(dm.type)

  // 5. Get base options (title, grid, legend)
  const base = getBaseOptions()

  // 6. Build chart-specific options based on type
  let specific: EChartsOption = {}
  try {
    if (t === 'pie_chart') {
      specific = buildPieOptions(rows, dm)
    }
    else if (t === 'bar_chart' || t === 'line_chart' || t === 'area_chart') {
      specific = buildCartesianOptions(rows, dm)
    }
    else if (t === 'scatter_plot') {
      specific = buildScatterOptions(rows, dm)
    }
    // ... other chart types

    // 7. Merge base + specific options
    const merged = { ...base, ...specific }

    // 8. Apply theme colors/gradients
    applyThemeColors(merged, t, dm)

    // 9. Set final options
    chartOptions.value = merged
  }
  catch (e) {
    chartOptions.value = { title: { text: 'Error Building Chart' } }
  }
  finally {
    isLoading.value = false
    chartKey.value++
  }
}
```

### Triggered by Data Changes

```typescript
// Watch for data changes and rebuild
watch(
  () => [props.step?.id, props.data?.rows, props.data_model, props.view, tokens.value],
  () => {
    buildOptions()
  },
  { deep: true, immediate: true }
)
```

---

## Complete Example: Backend to ECharts

### Backend DataFrame (Python)

```python
df = pd.DataFrame({
    'Region': ['North', 'South', 'East', 'West'],
    'Revenue': [150000, 180000, 210000, 120000],
    'Cost': [100000, 120000, 140000, 80000]
})
```

### Backend JSON (API Response)

```json
{
  "step": {
    "data": {
      "columns": [
        { "field": "Region", "headerName": "Region" },
        { "field": "Revenue", "headerName": "Revenue" },
        { "field": "Cost", "headerName": "Cost" }
      ],
      "rows": [
        { "Region": "North", "Revenue": 150000, "Cost": 100000 },
        { "Region": "South", "Revenue": 180000, "Cost": 120000 },
        { "Region": "East", "Revenue": 210000, "Cost": 140000 },
        { "Region": "West", "Revenue": 120000, "Cost": 80000 }
      ]
    },
    "data_model": {
      "type": "bar_chart",
      "series": [
        { "name": "Revenue", "key": "Region", "value": "Revenue" }
      ]
    }
  }
}
```

### Frontend Normalization Step 1

```javascript
// normalizeRows() converts keys to lowercase
const rows = [
  { region: "North", revenue: 150000, cost: 100000 },
  { region: "South", revenue: 180000, cost: 120000 },
  { region: "East", revenue: 210000, cost: 140000 },
  { region: "West", revenue: 120000, cost: 80000 }
]
```

### Frontend Normalization Step 2

```javascript
// buildCartesianOptions() extracts categories
const categoryKey = "region"  // from data_model.series[0].key.toLowerCase()
const categories = ["North", "South", "East", "West"]
```

### Frontend Normalization Step 3

```javascript
// buildCartesianOptions() maps series data
const valueKey = "revenue"  // from data_model.series[0].value.toLowerCase()
const data = categories.map(cat => {
  const row = rows.find(r => r[categoryKey] === cat)
  return row ? row[valueKey] : null
})
// data = [150000, 180000, 210000, 120000]
```

### Frontend Normalization Step 4

```javascript
// Build series object
const series = [{
  name: "Revenue",
  type: "bar",
  data: [150000, 180000, 210000, 120000]
}]
```

### Final ECharts Options

```javascript
{
  title: { text: "Revenue by Region", left: 'center', top: 5 },
  grid: { containLabel: true, left: 0, right: 0, bottom: 2, top: 40 },
  legend: { show: false },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: ["North", "South", "East", "West"],
    name: "Region"
  },
  yAxis: {
    type: 'value',
    name: 'Values'
  },
  series: [{
    name: "Revenue",
    type: "bar",
    data: [150000, 180000, 210000, 120000],
    itemStyle: {
      color: new LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: '#60a5fa' },
        { offset: 1, color: '#2563eb' }
      ])
    }
  }]
}
```

---

## Edge Cases Handled

### 1. Missing Values

```javascript
// Input
[
  { region: "North", revenue: 150000 },
  { region: "South", revenue: null },
  { region: "East", revenue: 210000 }
]

// After normalization (Number(null) = 0, but checked with isNaN)
const v = row ? Number(row[valueKey]) : null
return Number.isNaN(v) ? null : v

// Result: [150000, null, 210000]
// ECharts renders null as gap in chart
```

### 2. Extra Columns Ignored

```javascript
// Input has extra 'year' column
{ region: "North", revenue: 150000, year: 2024 }

// Only columns in data_model.series are used
// 'year' is normalized but not accessed
{ region: "North", revenue: 150000, year: 2024 }
//                                   ^^^^ Ignored
```

### 3. Duplicate Categories

```javascript
// Input with duplicates
[
  { region: "North", revenue: 150000 },
  { region: "North", revenue: 180000 },  // Duplicate!
  { region: "South", revenue: 200000 }
]

// new Set() deduplicates
const categories = Array.from(new Set(["North", "North", "South"]))
// categories = ["North", "South"]

// rows.find() returns FIRST match
const row = rows.find(r => r.region === "North")
// row = { region: "North", revenue: 150000 }
// Second "North" is ignored!
```

### 4. Non-numeric Values

```javascript
// Input has string in numeric column
{ region: "North", revenue: "invalid" }

// Number("invalid") = NaN
const v = Number(row[valueKey])  // NaN

// isNaN check catches it
return Number.isNaN(v) ? null : v  // Returns null

// Result in series: [null, ...]
// ECharts skips rendering this point
```

---

## Performance Optimizations

### 1. Single Pass Normalization

```javascript
// Efficient: One map operation
return rows.map(r => {
  const o: any = {}
  Object.keys(r).forEach(k => (o[k.toLowerCase()] = r[k]))
  return o
})

// vs. Inefficient: Multiple passes
const normalized = rows.map(r => lowercaseKeys(r))
const filtered = normalized.filter(r => isValid(r))
const transformed = filtered.map(r => transform(r))
```

### 2. Set for Unique Categories

```javascript
// Efficient: O(n) with Set
const categories = Array.from(new Set(rows.map(r => r[key])))

// vs. Inefficient: O(n²) with filter
const categories = rows
  .map(r => r[key])
  .filter((v, i, arr) => arr.indexOf(v) === i)
```

### 3. Lowercase Keys Once

```javascript
// Keys lowercased during normalization
const categoryKey = dm.series[0].key.toLowerCase()  // Once
const valueKey = dm.series[0].value.toLowerCase()    // Once

// Then used in loops without re-lowercasing
categories.map(cat => {
  const row = rows.find(r => r[categoryKey] === cat)  // Already lowercase
  return row[valueKey]  // Already lowercase
})
```

---

## Key Takeaways

1. **normalizeRows()** converts all row keys to lowercase for consistent access

2. **Categories extracted** using `Array.from(new Set(...))` for uniqueness

3. **Series data aligned** with categories using `categories.map()` + `rows.find()`

4. **Multiple series** each map independently to the same category array

5. **Null handling** preserves missing values as `null` in data arrays

6. **Type coercion** uses `Number()` with `isNaN()` check for safety

7. **Chart-specific builders** handle different data structures (pie vs cartesian)

8. **Single normalization pass** at the start optimizes performance

9. **Case-insensitive keys** prevent bugs from inconsistent backend casing

10. **Index alignment critical** - series data arrays MUST align with categories array

The normalization ensures **predictable, type-safe data** ready for ECharts rendering!
