# Linear Gradient Colors in ECharts Bars

**Location**: `frontend/components/dashboard/charts/EChartsVisual.vue` + `frontend/components/dashboard/themes/index.ts`

This document explains how linear gradient colors are applied to ECharts bars and other chart series.

---

## Overview: Gradient Flow

```
Theme Definition     →    Resolution Function    →    ECharts Object    →    Canvas Rendering
(palette array)          (resolveColorInput)         (LinearGradient)        (GPU/Canvas)
```

---

## Step 1: Theme Defines Gradient Palette

**Location**: `frontend/components/dashboard/themes/index.ts:9-15`

### Gradient Object Structure

```typescript
{
  type: 'linear',
  x: 0,      // Start X coordinate (0 = left, 1 = right)
  y: 0,      // Start Y coordinate (0 = top, 1 = bottom)
  x2: 0,     // End X coordinate
  y2: 1,     // End Y coordinate
  colorStops: [
    { offset: 0, color: '#60a5fa' },    // Start color (light blue)
    { offset: 1, color: '#2563eb' }     // End color (dark blue)
  ],
  global: false  // Relative to shape, not canvas
}
```

### Default Theme Palette

```typescript
palette: [
  // Blue: Vertical gradient (top to bottom)
  {
    type: 'linear',
    x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [
      { offset: 0, color: '#60a5fa' },  // Light blue at top
      { offset: 1, color: '#2563eb' }   // Dark blue at bottom
    ],
    global: false
  },

  // Emerald: Horizontal gradient (left to right)
  {
    type: 'linear',
    x: 0, y: 0, x2: 1, y2: 0,
    colorStops: [
      { offset: 0, color: '#34d399' },  // Light emerald at left
      { offset: 1, color: '#059669' }   // Dark emerald at right
    ],
    global: false
  },

  // Amber: Diagonal gradient (top-left to bottom-right)
  {
    type: 'linear',
    x: 0, y: 0, x2: 1, y2: 1,
    colorStops: [
      { offset: 0, color: '#fbbf24' },  // Light amber
      { offset: 1, color: '#f59e0b' }   // Dark amber
    ],
    global: false
  },

  // Rose: Diagonal gradient (bottom-left to top-right)
  {
    type: 'linear',
    x: 0, y: 1, x2: 1, y2: 0,
    colorStops: [
      { offset: 0, color: '#fb7185' },  // Pink at bottom
      { offset: 1, color: '#ef4444' }   // Red at top
    ],
    global: false
  },

  // Violet: Diagonal gradient (top-right to bottom-left)
  {
    type: 'linear',
    x: 1, y: 0, x2: 0, y2: 1,
    colorStops: [
      { offset: 0, color: '#a78bfa' },  // Light purple
      { offset: 1, color: '#7c3aed' }   // Dark purple
    ],
    global: false
  }
]
```

---

## Step 2: Gradient Coordinates Explained

### Coordinate System

The coordinates are **normalized** from 0 to 1:

```
(0,0) ───────────────── (1,0)
  │                        │
  │                        │
  │       Shape/Bar        │
  │                        │
  │                        │
(0,1) ───────────────── (1,1)
```

### Gradient Direction Examples

| x | y | x2 | y2 | Direction | Visual |
|---|---|----|----|-----------|--------|
| 0 | 0 | 0 | 1 | **Vertical (↓)** | Top to bottom |
| 0 | 1 | 0 | 0 | **Vertical (↑)** | Bottom to top |
| 0 | 0 | 1 | 0 | **Horizontal (→)** | Left to right |
| 1 | 0 | 0 | 0 | **Horizontal (←)** | Right to left |
| 0 | 0 | 1 | 1 | **Diagonal (↘)** | Top-left to bottom-right |
| 0 | 1 | 1 | 0 | **Diagonal (↗)** | Bottom-left to top-right |
| 1 | 0 | 0 | 1 | **Diagonal (↙)** | Top-right to bottom-left |
| 1 | 1 | 0 | 0 | **Diagonal (↖)** | Bottom-right to top-left |

### Visual Examples

#### Vertical Gradient (Default Blue)
```
x: 0, y: 0, x2: 0, y2: 1

    ┌────────┐
    │ #60a5fa│ ← Light blue at top (offset: 0)
    │        │
    │   ↓    │ ← Gradient flows downward
    │        │
    │ #2563eb│ ← Dark blue at bottom (offset: 1)
    └────────┘
```

#### Horizontal Gradient (Emerald)
```
x: 0, y: 0, x2: 1, y2: 0

    ┌──────────────────┐
    │ #34d399 → #059669│
    │  Light    Dark   │
    │  Left     Right  │
    └──────────────────┘
```

#### Diagonal Gradient (Amber)
```
x: 0, y: 0, x2: 1, y2: 1

    ┌────────────┐
    │#fbbf24    │ ← Light amber (top-left)
    │   ↘       │
    │     ↘     │ ← Diagonal flow
    │       ↘   │
    │        #f59e0b │ ← Dark amber (bottom-right)
    └────────────┘
```

---

## Step 3: Resolve Gradient to ECharts Object

**Location**: `frontend/components/dashboard/charts/EChartsVisual.vue:371-383`

### Resolution Function

```typescript
import { graphic as EGraphic } from 'echarts'

function resolveColorInput(input: any): any {
  // Return undefined if no input
  if (!input) return undefined

  // If it's a plain string color, return as-is
  if (typeof input === 'string') return input

  // If it's a gradient object, convert to ECharts LinearGradient
  if (typeof input === 'object' && Array.isArray(input.colorStops)) {
    const x = Number(input.x ?? 0)
    const y = Number(input.y ?? 0)
    const x2 = Number(input.x2 ?? 1)
    const y2 = Number(input.y2 ?? 0)

    // Create ECharts LinearGradient instance
    return new EGraphic.LinearGradient(x, y, x2, y2, input.colorStops)
  }

  // Return as-is for other types
  return input
}
```

### What `new EGraphic.LinearGradient()` Does

Creates an ECharts LinearGradient object:

```javascript
new EGraphic.LinearGradient(
  0,     // x: start X
  0,     // y: start Y
  0,     // x2: end X
  1,     // y2: end Y
  [
    { offset: 0, color: '#60a5fa' },
    { offset: 1, color: '#2563eb' }
  ]
)
```

**ECharts LinearGradient Class**:
- Part of `echarts/core` graphics module
- Extends `zrender` (ECharts' rendering engine) gradient types
- Supports canvas and SVG rendering
- Handles coordinate transformations automatically

---

## Step 4: Apply Gradients to Chart Series

**Location**: `frontend/components/dashboard/charts/EChartsVisual.vue:398-428`

### Color Application Flow

```typescript
function applyThemeColors(option: EChartsOption, type: string, dm: any) {
  // 1. Get palette from theme
  let pal = paletteArray()  // Returns theme's palette array

  // 2. Allow view to override theme palette
  const viewColors = (props.view?.options as any)?.colors
  if (Array.isArray(viewColors) && viewColors.length) {
    pal = viewColors
  }

  // 3. Return if no series
  if (!Array.isArray(option.series)) return

  // 4. Apply to bar/line/area charts
  if (type === 'bar_chart' || type === 'line_chart' || type === 'area_chart') {
    option.series = option.series.map((s: any, i: number) => {
      // Get gradient from palette (cycle if more series than colors)
      const color = resolveColorInput(pal[i % pal.length])

      // Apply to series itemStyle
      const next = {
        ...s,
        itemStyle: {
          ...(s.itemStyle || {}),
          color  // ← LinearGradient object or string
        }
      }

      // For area charts, also apply to areaStyle
      if (s.type === 'line' && dm?.type === 'area_chart') {
        next.areaStyle = {
          ...(s.areaStyle || {}),
          color
        }
      }

      return next
    })
    return
  }

  // 5. Apply to pie charts (per slice)
  if (type === 'pie_chart') {
    option.series[0].data = option.series[0].data.map((d: any, i: number) => ({
      ...d,
      itemStyle: {
        color: resolveColorInput(pal[i % pal.length])
      }
    }))
  }
}
```

### Series Index Cycling

If you have more series than palette colors, they cycle:

```typescript
// Palette has 5 gradients: [blue, emerald, amber, rose, violet]
const color = resolveColorInput(pal[i % pal.length])

// Series 0: pal[0 % 5] = pal[0] = blue gradient
// Series 1: pal[1 % 5] = pal[1] = emerald gradient
// Series 2: pal[2 % 5] = pal[2] = amber gradient
// Series 3: pal[3 % 5] = pal[3] = rose gradient
// Series 4: pal[4 % 5] = pal[4] = violet gradient
// Series 5: pal[5 % 5] = pal[0] = blue gradient (cycles back)
```

---

## Step 5: Final ECharts Options with Gradients

### Complete Example

**Input Data**:
```json
{
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
```

**After `buildCartesianOptions()` + `applyThemeColors()`**:
```javascript
{
  title: { text: "Revenue by Region" },
  xAxis: {
    type: "category",
    data: ["North", "South"]
  },
  yAxis: { type: "value" },
  series: [
    {
      name: "Revenue",
      type: "bar",
      data: [150000, 180000],
      itemStyle: {
        color: new EGraphic.LinearGradient(
          0, 0, 0, 1,  // Vertical gradient
          [
            { offset: 0, color: '#60a5fa' },  // Light blue at top
            { offset: 1, color: '#2563eb' }   // Dark blue at bottom
          ]
        )
      }
    }
  ]
}
```

**Visual Result**:
```
    Revenue by Region
    ─────────────────
200K │
     │     ┌─────┐
180K │     │ ░░░ │ ← #60a5fa (light blue)
     │     │ ▒▒▒ │
160K │     │ ▓▓▓ │
     │     │ ███ │ ← #2563eb (dark blue)
140K │┌─────┤ ███ │
     ││ ░░░ │ ███ │
120K ││ ▒▒▒ │ ███ │
     ││ ▓▓▓ │ ███ │
100K ││ ███ │ ███ │
     │└─────┴─────┘
      North  South
```

---

## Step 6: Canvas Rendering

### How ECharts Renders Gradients

1. **ECharts receives LinearGradient object**
2. **Converts to Canvas API gradient**:
   ```javascript
   const ctx = canvas.getContext('2d')
   const gradient = ctx.createLinearGradient(
     x * width,      // Start X in pixels
     y * height,     // Start Y in pixels
     x2 * width,     // End X in pixels
     y2 * height     // End Y in pixels
   )
   gradient.addColorStop(0, '#60a5fa')
   gradient.addColorStop(1, '#2563eb')
   ctx.fillStyle = gradient
   ctx.fillRect(...)  // Draw bar
   ```

3. **GPU accelerated rendering** (if available)
4. **Result**: Smooth color transition on canvas

---

## Theme-Specific Gradients

### Default Theme
- **Style**: Modern, vibrant
- **Gradients**: Mix of vertical, horizontal, and diagonal
- **Colors**: Blue, emerald, amber, rose, violet

### Retro Theme
- **Style**: Warm 70s poster vibes
- **Gradients**: Horizontal and diagonal focus
- **Colors**: Mustard, avocado, sunflower, magenta, cornflower

```typescript
palette: [
  { type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
    colorStops: [
      { offset: 0, color: '#F59E0B' },  // Mustard
      { offset: 1, color: '#D97706' }   // Burnt orange
    ]
  },
  // ... more gradients
]
```

### Hacker Theme
- **Style**: Dark ops dashboard with neon accents
- **Gradients**: High contrast, tech-inspired
- **Colors**: Neon green, teal, orange, violet, amber

```typescript
palette: [
  { type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
    colorStops: [
      { offset: 0, color: '#22c55e' },  // Neon green
      { offset: 1, color: '#16a34a' }   // Forest green
    ]
  },
  // ... more gradients
]
```

### Research Theme
- **Style**: Clean, academic
- **Gradients**: None! Uses solid colors
- **Colors**: Plain hex strings

```typescript
palette: [
  '#2563eb',  // Solid blue
  '#0ea5e9',  // Solid cyan
  '#059669',  // Solid emerald
  '#7c3aed',  // Solid purple
  '#f59e0b'   // Solid amber
]
```

---

## Custom Gradients via View Overrides

### Override in Widget View

You can override the theme's palette per-widget:

```typescript
// In widget.view or visualization.view
{
  type: "bar_chart",
  options: {
    colors: [
      // Custom gradient
      {
        type: 'linear',
        x: 0, y: 1, x2: 1, y2: 0,  // Bottom-left to top-right
        colorStops: [
          { offset: 0, color: '#ff0000' },  // Red
          { offset: 0.5, color: '#ffff00' },  // Yellow (midpoint)
          { offset: 1, color: '#00ff00' }   // Green
        ],
        global: false
      },
      // Plain color
      '#0000ff'
    ]
  }
}
```

### Three-Color Gradient

```typescript
{
  type: 'linear',
  x: 0, y: 0, x2: 0, y2: 1,
  colorStops: [
    { offset: 0, color: '#ef4444' },    // Red at top (0%)
    { offset: 0.5, color: '#fbbf24' },  // Amber in middle (50%)
    { offset: 1, color: '#22c55e' }     // Green at bottom (100%)
  ],
  global: false
}
```

**Visual**:
```
    ┌────────┐
    │  Red   │ ← offset: 0
    │ ──────→│
    │ Amber  │ ← offset: 0.5
    │ ──────→│
    │ Green  │ ← offset: 1
    └────────┘
```

---

## Advanced: Global vs Local Gradients

### `global: false` (Default)
Gradient is relative to **each individual bar/shape**:

```
Bar 1    Bar 2    Bar 3
┌───┐   ┌───┐   ┌───┐
│ ░ │   │ ░ │   │ ░ │ ← Each starts light
│ ▒ │   │ ▒ │   │ ▒ │
│ ▓ │   │ ▓ │   │ ▓ │
│ █ │   │ █ │   │ █ │ ← Each ends dark
└───┘   └───┘   └───┘
```

### `global: true`
Gradient is relative to **entire canvas**:

```
Canvas-wide gradient (rarely used):
┌──────────────────────┐
│ Light                │ ← Top of canvas
│  ┌───┐   ┌───┐   ┌───┐
│  │ ░ │   │ ▒ │   │ ▓ │ ← Bars sample gradient
│  │ ░ │   │ ▒ │   │ ▓ │
│  │ ░ │   │ ▒ │   │ ▓ │
│  └───┘   └───┘   └───┘
│                    Dark│ ← Bottom of canvas
└──────────────────────┘
```

**Note**: The system uses `global: false` everywhere for consistent per-bar gradients.

---

## Pie Chart Gradients

Pie charts apply gradients per **slice**:

```typescript
if (type === 'pie_chart') {
  option.series[0].data = option.series[0].data.map((d: any, i: number) => ({
    ...d,
    itemStyle: {
      color: resolveColorInput(pal[i % pal.length])
    }
  }))
}
```

**Result**:
```
      ╱─────╲
    ╱    ░    ╲     Slice 1: Blue gradient
   │  ░ ▒ ▓    │    (radial-like effect from gradient)
   │ ░ ▒ ▓ █   │
    ╲  ▒ ▓ █  ╱     Slice 2: Emerald gradient
      ╲─────╱
```

---

## Area Chart Gradients

Area charts apply gradients to **both line and area fill**:

```typescript
if (s.type === 'line' && dm?.type === 'area_chart') {
  next.areaStyle = {
    ...(s.areaStyle || {}),
    color  // ← Same gradient as line
  }
}
```

**Result**:
```
     ╱╲       Light color
    ╱  ╲   ╱
   ╱ ░░ ╲ ╱   ← Gradient fills area
  ╱ ░▒▓█ ╲╱
 ╱──────────  Dark color at bottom
```

---

## Debugging Gradients

### Check Theme Palette

```typescript
// In browser console
const { tokens } = useDashboardTheme('default', {}, null)
console.log(tokens.value.palette)
```

### Inspect Resolved Color

```typescript
const gradientDef = {
  type: 'linear',
  x: 0, y: 0, x2: 0, y2: 1,
  colorStops: [
    { offset: 0, color: '#60a5fa' },
    { offset: 1, color: '#2563eb' }
  ]
}
const resolved = resolveColorInput(gradientDef)
console.log(resolved)
// Output: LinearGradient { x: 0, y: 0, x2: 0, y2: 1, colorStops: [...] }
```

### View ECharts Options

```typescript
// In EChartsVisual.vue
watch(chartOptions, (options) => {
  console.log('ECharts Options:', options)
  console.log('Series color:', options.series[0].itemStyle.color)
})
```

---

## Key Takeaways

1. **Gradients are theme-configurable**: Each theme defines a palette array of gradient objects

2. **Coordinates are normalized**: (0,0) to (1,1) system works for any bar size

3. **Direction variety**: Vertical, horizontal, and 4 diagonal directions create visual interest

4. **Per-bar gradients**: `global: false` ensures each bar has full gradient range

5. **Cycle for multiple series**: Palette colors repeat using modulo operator

6. **ECharts LinearGradient**: Native class handles canvas rendering automatically

7. **Override anywhere**: Can override theme palette at widget level via `view.options.colors`

8. **Solid colors supported**: Plain hex strings work alongside gradient objects

9. **Area charts inherit**: Line chart gradients automatically apply to area fill

10. **Multi-stop gradients**: Can use 3+ color stops for complex transitions

The gradient system provides **beautiful, customizable visualizations** with minimal configuration!
