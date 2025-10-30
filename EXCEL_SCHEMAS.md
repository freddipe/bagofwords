# Excel Files as Schemas in Bag of Words

When the data source is an **Excel file** instead of a database, schemas work differently. Here's the complete explanation.

---

## Key Difference: Excel vs Database

| Aspect | Database | Excel |
|--------|----------|-------|
| **Schema Source** | Database metadata (INFORMATION_SCHEMA) | AI-analyzed spreadsheet structure |
| **Storage** | `datasource_tables` table | `sheet_schemas` table (linked to `files`) |
| **Structure** | Fixed tables/columns | Variable layouts (headers in any row, vertical/horizontal data) |
| **Query Method** | SQL | pandas `read_excel()` with cell ranges |
| **Schema Generation** | Direct introspection | LLM analyzes sample data |

---

## How Excel Schemas Are Generated

### 1. File Upload

User uploads an Excel file (`.xlsx`, `.xls`)

### 2. Excel Agent Analyzes Each Sheet

**Location**: `backend/app/ai/agents/excel/excel.py:24`

```python
class ExcelAgent:
    def get_schema(self, index):
        # 1. Read first 200x200 cells of sheet
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        df_subset = df.iloc[0:200, 0:200].to_dict(orient='split')

        # 2. Send to LLM for analysis
        prompt = f"""
        excel_name: {filename}
        sheet name: {sheet_name}
        sheet index: {index}
        excel dict: {df_subset}

        Given this excel sample, please review and provide the following.
        You need to generate a json schema for the excel file.
        You need to identify all columns, metrics, and fields -- and for each
        of these you need to find the exact cell address, range, orientation, and type.

        The schema should be in the following format:
        {{
          sheet_name: "sheetname",
          sheet_index: [number],
          sheet_file_path: {path},
          fields: {{
            "field_name": "NAME!",
            "data": {{
              type: "int/dec/string/date/boolean",
              cell_address: "A2",
              orientation: "vertical/horizontal",
              range: "A2:A100"
            }}
          }}
        }}

        Respond with only the json schema, no other text.
        """

        schema = self.llm.inference(prompt)
        return json.loads(schema)
```

### 3. Schema Stored in Database

**Model**: `backend/app/models/sheet_schema.py`

```python
class SheetSchema(BaseSchema):
    __tablename__ = "sheet_schemas"

    schema = Column(JSON)           # The generated schema
    sheet_name = Column(String)     # "Budget", "Actuals", etc.
    sheet_index = Column(Integer)   # 0, 1, 2...
    file_id = Column(String)        # FK to files table
```

**Example stored schema:**
```json
{
  "sheet_name": "Q4_Budget",
  "sheet_index": 0,
  "sheet_file_path": "/uploads/budget_2024.xlsx",
  "fields": {
    "region": {
      "data": {
        "type": "string",
        "cell_address": "A2",
        "orientation": "vertical",
        "range": "A2:A20"
      }
    },
    "budget_amount": {
      "data": {
        "type": "dec",
        "cell_address": "B2",
        "orientation": "vertical",
        "range": "B2:B20"
      }
    },
    "month": {
      "data": {
        "type": "date",
        "cell_address": "C1",
        "orientation": "horizontal",
        "range": "C1:N1"
      }
    }
  }
}
```

---

## How Excel Schemas Are Passed to Coder

### 1. File Model's Description Property

**Location**: `backend/app/models/file.py:44`

```python
class File(BaseSchema):
    @property
    def description(self):
        if self.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            description = f"File: {self.filename} at {self.path}\n\nSheet Schemas:\n"
            for sheet_schema in self.sheet_schemas:
                description += f"Sheet Name: {sheet_schema.sheet_name}\n"
                description += f"Sheet index: {sheet_schema.sheet_index}\n"
        return description

    def prompt_schema(self):
        context = []
        if self.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            for sheet_schema in self.sheet_schemas:
                context.append(f"Sheet Name: {sheet_schema.sheet_name}")
                context.append(sheet_schema.schema)
            text = f"File: {self.filename} \nPath: {self.path}\n\nSheet Schemas: {context}"
        return text
```

### 2. FilesContextBuilder

**Location**: `backend/app/ai/context/builders/files_context_builder.py:14`

```python
class FilesContextBuilder:
    async def build(self) -> FilesSchemaContext:
        files = self.report.files
        items = []
        for f in files:
            items.append(
                FilesSchemaContext.FileItem(
                    id=str(f.id),
                    filename=f.filename,
                    path=f.path,
                    content_type=f.content_type,
                    prompt_schema=f.prompt_schema()  # ← Uses schema
                )
            )
        return FilesSchemaContext(files=items)
```

### 3. Rendered as XML

**Location**: `backend/app/ai/context/sections/files_schema_section.py:19`

```python
def render(self) -> str:
    file_nodes = []
    for f in self.files:
        inner = xml_tag("schema", xml_escape(f.prompt_schema))
        file_nodes.append(
            xml_tag("file", inner, {
                "id": f.id,
                "filename": f.filename,
                "path": f.path,
                "content_type": f.content_type
            })
        )
    return xml_tag("files", "\n\n".join(file_nodes))
```

---

## Example: Excel Schema in Coder Prompt

### Uploaded File: `budget_2024.xlsx`

**Sheet 0: "Q4_Budget"**
```
     A          B           C      D      E
1  Region   Budget    Oct    Nov    Dec
2  North    150000   50000  50000  50000
3  South    120000   40000  40000  40000
4  East     180000   60000  60000  60000
5  West     95000    30000  32000  33000
```

### Generated Schema (by LLM)

```json
{
  "sheet_name": "Q4_Budget",
  "sheet_index": 0,
  "sheet_file_path": "/uploads/budget_2024.xlsx",
  "fields": {
    "region": {
      "data": {
        "type": "string",
        "cell_address": "A2",
        "orientation": "vertical",
        "range": "A2:A5"
      }
    },
    "budget": {
      "data": {
        "type": "int",
        "cell_address": "B2",
        "orientation": "vertical",
        "range": "B2:B5"
      }
    },
    "oct": {
      "data": {
        "type": "int",
        "cell_address": "C2",
        "orientation": "vertical",
        "range": "C2:C5"
      }
    },
    "nov": {
      "data": {
        "type": "int",
        "cell_address": "D2",
        "orientation": "vertical",
        "range": "D2:D5"
      }
    },
    "dec": {
      "data": {
        "type": "int",
        "cell_address": "E2",
        "orientation": "vertical",
        "range": "E2:E5"
      }
    }
  }
}
```

### Rendered in Coder Prompt

```xml
<files>
  <file
    id="uuid-789"
    filename="budget_2024.xlsx"
    path="/uploads/budget_2024.xlsx"
    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet">
    <schema>
      File: budget_2024.xlsx
      Path: /uploads/budget_2024.xlsx

      Sheet Schemas:
      Sheet Name: Q4_Budget
      {
        "sheet_name": "Q4_Budget",
        "sheet_index": 0,
        "fields": {
          "region": {"data": {"type": "string", "cell_address": "A2", "orientation": "vertical", "range": "A2:A5"}},
          "budget": {"data": {"type": "int", "cell_address": "B2", "orientation": "vertical", "range": "B2:B5"}},
          "oct": {"data": {"type": "int", "cell_address": "C2", "orientation": "vertical", "range": "C2:C5"}},
          "nov": {"data": {"type": "int", "cell_address": "D2", "orientation": "vertical", "range": "D2:D5"}},
          "dec": {"data": {"type": "int", "cell_address": "E2", "orientation": "vertical", "range": "E2:E5"}}
        }
      }
    </schema>
  </file>
</files>
```

---

## How Coder Uses Excel Schemas

### User Request
"Compare actual sales to budget by region"

### Coder Receives Context

**Database Schema:**
```xml
<schemas>
  <data_source name="Sales DB" type="postgresql">
    <table name="sales">
      <column name="region" dtype="VARCHAR"/>
      <column name="amount" dtype="DECIMAL"/>
    </table>
  </data_source>
</schemas>
```

**Excel File Schema:**
```xml
<files>
  <file filename="budget_2024.xlsx" path="/uploads/budget_2024.xlsx">
    <schema>
      Sheet Name: Q4_Budget
      Fields: region (A2:A5), budget (B2:B5), oct (C2:C5), nov (D2:D5), dec (E2:E5)
    </schema>
  </file>
</files>
```

### Generated Code

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Get actual sales from database
    sales_df = ds_clients['Sales DB'].execute_query("""
        SELECT
            region,
            SUM(amount) as actual_sales
        FROM sales
        WHERE sale_date >= '2024-10-01' AND sale_date <= '2024-12-31'
        GROUP BY region
    """)
    print("Sales df head:", sales_df.head())

    # Read budget from Excel
    budget_df = pd.read_excel(
        excel_files[0].path,
        sheet_name=0,  # Q4_Budget sheet
        header=0       # First row is header
    )

    # Select only region and total budget columns
    budget_df = budget_df[['Region', 'Budget']]
    budget_df.columns = ['region', 'budget']

    print("Budget df head:", budget_df.head())

    # Merge actual and budget
    comparison_df = pd.merge(
        sales_df,
        budget_df,
        on='region',
        how='outer'
    )

    # Calculate variance
    comparison_df['variance'] = comparison_df['actual_sales'] - comparison_df['budget']
    comparison_df['variance_pct'] = (comparison_df['variance'] / comparison_df['budget']) * 100

    comparison_df = comparison_df.sort_values('variance', ascending=False)

    print("Final df Preview:", comparison_df.head())
    return comparison_df
```

---

## Coder Prompt Instructions for Excel

**From**: `backend/app/ai/agents/coder/coder.py:203`

```python
"""
- Excel Files:
<excel_files>
{excel_files_section}
</excel_files>

- For Excel files, use `pd.read_excel(excel_files[INDEX].path, sheet_name=SHEET_INDEX, header=None)` to read data.
  * Decide the correct INDEX and SHEET_INDEX based on prompt and data model.
  * Print the dict/df preview to help the LLM ensure indices and positions are correct.
"""
```

**Excel Files Section Format:**
```
0: budget_2024.xlsx (Sheet 0: Q4_Budget, Sheet 1: Actuals)
1: targets.xlsx (Sheet 0: Annual_Targets)
```

---

## Complex Excel Example: Horizontal Layout

### File: `monthly_metrics.xlsx`

**Sheet: "KPIs"**
```
     A             B      C      D      E
1  Metric      Jan    Feb    Mar    Apr
2  Revenue     100k   120k   115k   130k
3  Customers   500    550    525    600
4  Orders      1200   1400   1350   1500
```

### Generated Schema

```json
{
  "sheet_name": "KPIs",
  "sheet_index": 0,
  "fields": {
    "metric_names": {
      "data": {
        "type": "string",
        "cell_address": "A2",
        "orientation": "vertical",
        "range": "A2:A4"
      }
    },
    "jan": {
      "data": {
        "type": "string",
        "cell_address": "B2",
        "orientation": "vertical",
        "range": "B2:B4"
      }
    },
    "feb": {
      "data": {
        "type": "string",
        "cell_address": "C2",
        "orientation": "vertical",
        "range": "C2:C4"
      }
    }
    // ... etc
  }
}
```

### Generated Code (Handles Horizontal Layout)

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Read Excel with first row as header
    df = pd.read_excel(
        excel_files[0].path,
        sheet_name=0,
        header=0,
        index_col=0  # Use first column (Metric) as index
    )

    print("Raw df:", df.head())

    # Transpose to make months into rows
    df_transposed = df.T
    df_transposed = df_transposed.reset_index()
    df_transposed.columns = ['month', 'revenue', 'customers', 'orders']

    # Clean revenue values (remove 'k' suffix and convert)
    df_transposed['revenue'] = df_transposed['revenue'].str.replace('k', '').astype(float) * 1000

    print("Final df Preview:", df_transposed.head())
    return df_transposed
```

---

## Advantages of AI-Generated Excel Schemas

### 1. **Handles Irregular Layouts**

Unlike databases with fixed structure, Excel can have:
- Headers in any row
- Data starting at any cell
- Multiple tables in one sheet
- Merged cells
- Pivot table formats

The LLM analyzes the **actual layout** and generates appropriate instructions.

### 2. **Type Detection**

LLM infers data types from values:
- `"100k"` → string (needs parsing)
- `100000` → int
- `100000.50` → dec
- `"2024-01-01"` → date

### 3. **Orientation Awareness**

Detects if data flows:
- **Vertical** (common): Headers in row 1, data in rows below
- **Horizontal** (less common): Headers in column A, data in columns to the right

---

## Limitations

### 1. **No Usage Statistics**

Unlike database tables, Excel files don't have:
- ❌ Usage count
- ❌ Success rate
- ❌ User feedback
- ❌ Scoring/ranking

All Excel files are treated equally.

### 2. **Schema Generation Cost**

Each sheet requires:
- LLM inference call (costs tokens + time)
- Only first 200x200 cells analyzed (may miss data in large sheets)

### 3. **No Relationships**

Unlike database foreign keys, Excel has no formalized relationships between sheets or files.

### 4. **Schema May Be Stale**

If Excel file is updated after upload, schema isn't automatically refreshed.

---

## Complete Prompt Example: Database + Excel

**User**: "Show sales vs budget by region"

**Coder Receives:**

```
<schemas>
  <data_source name="Sales DB" type="postgresql" id="uuid-123">
    <table name="sales">
      <columns>
        <column name="region" dtype="VARCHAR"/>
        <column name="amount" dtype="DECIMAL"/>
        <column name="sale_date" dtype="DATE"/>
      </columns>
      <metrics>
        <score value="0.923"/>
        <usage count="250" success="245" failure="5"/>
      </metrics>
    </table>
  </data_source>
</schemas>

<files>
  <file id="uuid-789" filename="budget_2024.xlsx" path="/uploads/budget_2024.xlsx">
    <schema>
      File: budget_2024.xlsx
      Path: /uploads/budget_2024.xlsx

      Sheet Schemas:
      Sheet Name: Q4_Budget
      Sheet index: 0
      {
        "fields": {
          "region": {"type": "string", "range": "A2:A5"},
          "budget": {"type": "int", "range": "B2:B5"}
        }
      }
    </schema>
  </file>
</files>

- Data Sources and Clients:
data_source_name: Sales DB
description: PostgreSQL database. Use: client.execute_query('SELECT ...')

- Excel Files:
0: budget_2024.xlsx (Sheet 0: Q4_Budget)
```

**LLM Generates:**
```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Query database for actual sales
    sales_df = ds_clients['Sales DB'].execute_query("""
        SELECT region, SUM(amount) as actual
        FROM sales
        WHERE sale_date >= '2024-10-01'
        GROUP BY region
    """)

    # Read Excel for budget
    budget_df = pd.read_excel(excel_files[0].path, sheet_name=0)
    budget_df = budget_df[['Region', 'Budget']]
    budget_df.columns = ['region', 'budget']

    # Merge
    df = pd.merge(sales_df, budget_df, on='region', how='left')
    return df
```

---

## Key Takeaways

1. **Excel schemas are AI-generated** - LLM analyzes sample data to identify structure
2. **Stored per sheet** - Each sheet has its own schema in `sheet_schemas` table
3. **Includes cell ranges** - Specifies exact locations (e.g., "A2:A5")
4. **Handles irregular layouts** - Detects vertical/horizontal orientations
5. **Passed separately** - Excel files in `<files>` section, not `<schemas>`
6. **No usage stats** - Unlike database tables, no ranking/scoring
7. **Combined with databases** - Can merge Excel + SQL data in one widget

Excel schemas provide the Coder with enough information to correctly read spreadsheet data, even with non-standard layouts, by giving precise cell addresses and data orientations!
