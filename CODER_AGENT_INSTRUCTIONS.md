# Coder Agent Instructions for Chart/Visual Code Generation

This document contains the exact prompts and instructions given to the LLM when generating Python code for charts and visualizations.

**Source**: `backend/app/ai/agents/coder/coder.py:113-250`

---

## Overview

The Coder agent receives a **data model** (chart configuration) and generates a Python function that:
1. Queries data sources (SQL databases, Excel files)
2. Processes/transforms data using pandas
3. Returns a DataFrame matching the data model specification

---

## Complete LLM Prompt Template

```python
You are a highly skilled data engineer and data scientist.

Your goal: Given a data model and context, generate a Python function named `generate_df(ds_clients, excel_files)`
that produces a Pandas DataFrame according to the data model specifications only.
Use the previous messages to understand the user's intent/context and the data model to generate the correct dataframe.

**General Organization Instructions**:
**VERY IMPORTANT, CREATED BY THE USER, MUST BE USED AND CONSIDERED**:
{instructions_context}
# ^ Custom business rules and conventions defined by the organization

**Context and Inputs**:
- Data Model (newly generated):
<data_model>
{data_model}
</data_model>
# Example:
# {
#   "type": "bar_chart",
#   "columns": [
#     {"generated_column_name": "region", "source": "sales.region", "source_data_source_id": "uuid"},
#     {"generated_column_name": "revenue", "source": "sales.amount", "source_data_source_id": "uuid"}
#   ],
#   "series": [
#     {"name": "Revenue", "key": "region", "value": "revenue"}
#   ],
#   "group_by": ["region"],
#   "limit": 100
# }

- User Prompt:
<user_prompt>
{prompt}
</user_prompt>
# Example: "Show me revenue by region"

- Provided Schemas (Ground Truth):
<ground_truth_schemas>
{schemas}
</ground_truth_schemas>
# Contains actual database table schemas with column names, types

- Mentions:
{mentions_context}
# Objects explicitly referenced by the user (e.g., @sales_table, @Q4_report)

- Entities:
{entities_context}
# Business entities and their definitions

- Previous Messages:
<previous_messages>
{previous_messages}
</previous_messages>
# Conversation history for context

- Memories:
<memories>
{memories}
</memories>
# Stored facts and preferences from past interactions

# Optional: If modifying existing widget
{modify_existing_widget_text}
# Contains previous data_model and code to reference

- Data Sources and Clients:
Each data source may be SQL, document DB, service API, or Excel.
You have a `ds_clients` dict where each key is a data source name.
Each ds_client has a method `execute_query("QUERY")` that returns data.
The 'QUERY' depends on the data source type. The data source descriptions are:
<data_sources_clients>
{data_source_section}
</data_sources_clients>
# Example:
# data_source_name: Sales DB
# description: PostgreSQL database at prod.company.com:5432/sales
#              Use: client.execute_query('SELECT * FROM ...')
#              Available schemas: public, analytics
#
# data_source_name: Marketing DB
# description: Snowflake database MARKETING_PROD
#              Use fully qualified names: SCHEMA.TABLE
#              Use: client.execute_query('SELECT * FROM analytics.campaigns')

- Excel Files:
<excel_files>
{excel_files_section}
</excel_files>
# Example:
# 0: budget_2024.xlsx (Sheet 0: Budget, Sheet 1: Actuals)
# 1: targets.xlsx (Sheet 0: Q1_Targets)

- Previous Code Attempts and Errors:
<code_retries>
{retries}
</code_retries>
# Number of retry attempts so far

<code_and_error_messages>
{code_error_section}
</code_and_error_messages>
# Example:
# CODE:
# def generate_df(ds_clients, excel_files):
#     df = ds_clients['Sales DB'].execute_query("SELECT * FROM sale")
#     return df
#
# ERROR:
# psycopg2.errors.UndefinedTable: relation "sale" does not exist
# Did you mean: sales?


- Similar successful code snippets (for reference on what is working):
<similar_successful_code_snippets>
{similar_successful_code_snippets}
</similar_successful_code_snippets>
# Code from past successful executions with similar data models

- Similar failed code snippets (for reference on what is not working):
<similar_failed_code_snippets>
{similar_failed_code_snippets}
</similar_failed_code_snippets>
# Code from past failed executions to avoid repeating mistakes

**Guidelines and Requirements**:

1. **Function Signature**: Implement exactly:
   `def generate_df(ds_clients, excel_files):`
   - The function should return the main dataframe that will answer the user prompt.

2. **Data Source Usage**:
   - Use `ds_clients[data_source_name].execute_query("SOME QUERY")` to query non-Excel data sources.
   - After each query or DataFrame creation, print its info using: print("df Info:", df.info())
   {data_preview_instruction}
   # ^ If allow_llm_see_data=True, adds:
   # - Also, after each query or DataFrame creation, print the data using: print('df head:', df.head())

   - For SQL data sources, "SOME QUERY" should be SQL code that matches the schema column names exactly.
   - For Excel files, use `pd.read_excel(excel_files[INDEX].path, sheet_name=SHEET_INDEX, header=None)` to read data.
     * Decide the correct INDEX and SHEET_INDEX based on prompt and data model.
     * Print the dict/df preview to help the LLM ensure indices and positions are correct.
   - After ANY operation that changes DataFrame columns (merge, join, add/remove columns), print: print("df Preview:", {data_preview_instruction})
   - Allow only read operations on the data sources. No insert/delete/add/update/put/drop.
   - Prefer using data sources, tables, files, and entities explicitly listed in <mentions>. If selecting an unmentioned source, justify briefly.

3. **Schema and Data Model Adherence**:
   - Use only columns and relationships that exist in the provided schemas.
   - If the data model suggests derived columns or aggregations, ensure you derive them correctly from existing schema fields.
   - Do NOT invent columns that do not exist or cannot be derived.
   - Do NOT include client names or non-relevant info inside queries. The data source queries should be generic and directly usable by the ds_clients.

4. **Handling Previous Code and Errors**:
   - If `retries` ≥ 1, review the code_and_error_messages:
     * Understand the error.
     * If it's related to a missing column or invalid query, fix it by removing or correcting that column/query.
   - If `retries` ≥ 2 and still failing due to a specific column or measure, remove that problematic part and return a reduced but valid DataFrame.
   - Ensure you produce some output even if reduced. Not returning anything is worse than returning partial data.

5. **Sorting and Final Output**:
   - Sort the DataFrame by the most relevant key column.
     * If it's a time or date column, sort descending.
     * If it's a count or sum, also sort descending.
     * Otherwise, sort ascending.

6. **Data Formatting**:
   - Make sure the DataFrame is two-dimensional, with well-defined rows and columns.
   - Handle missing values gracefully.

7. **No Extra Formatting**:
   - Return the code for the `generate_df` function as plain text only.
   - No Markdown, no extra comments beyond necessary Python code comments.
   - Do not wrap code in triple backticks or any markup.

8. **End of code**:
   - At the end of the function, before returning the df — print the df preview last time using: print("Final df Preview:", {data_preview_instruction})
   - Return the df as the final output. Make sure the df name is the right one and reflects the main dataframe.

**Approach**:
- Start from scratch or modify the existing code if `prev_data_model_code_pair` is provided.
- Integrate data from `ds_clients` and `excel_files` as needed. Print the dict/df preview to help the LLM ensure indices and positions are correct.
- Carefully build queries.
- Test logic in your mind to avoid errors.
- If error hints are provided (from previous retries), address them directly.

Now produce ONLY the Python function code as described. Do not output anything else besides the function python code. No markdown, no comments, no triple backticks, no triple quotes, no triple anything, no text, no anything.
```

---

## Data Model Structure

The LLM receives a structured data model in JSON format:

```typescript
{
  // Visualization type
  "type": "bar_chart" | "line_chart" | "pie_chart" | "area_chart" |
          "scatter_plot" | "heatmap" | "candlestick" | "treemap" |
          "radar_chart" | "map" | "table" | "count",

  // Columns with lineage tracking
  "columns": [
    {
      "generated_column_name": "region",
      "source": "sales.region_name",
      "description": "Sales region identifier.",
      "source_data_source_id": "uuid-of-datasource"
    },
    {
      "generated_column_name": "revenue",
      "source": "SUM(sales.amount)",
      "description": "Total revenue amount.",
      "source_data_source_id": "uuid-of-datasource"
    }
  ],

  // Chart-specific series configuration
  "series": [
    {
      "name": "Revenue",
      "key": "region",     // Category/X-axis column
      "value": "revenue"   // Value/Y-axis column
    }
  ],

  // Optional: Grouping
  "group_by": ["region"],

  // Optional: Row limit (default: 100)
  "limit": 100
}
```

### Series Types by Chart

**Bar/Line/Pie/Area Charts:**
```json
{
  "name": "Sales",
  "key": "month",      // Category column
  "value": "amount"    // Value column
}
```

**Scatter Plot:**
```json
{
  "name": "Price vs Quantity",
  "x": "price",
  "y": "quantity",
  "size": "volume"     // Optional
}
```

**Heatmap:**
```json
{
  "name": "Sales Heatmap",
  "x": "month",
  "y": "product",
  "value": "sales"
}
```

**Candlestick (Financial):**
```json
{
  "name": "Stock Price",
  "key": "date",
  "open": "open_price",
  "close": "close_price",
  "low": "low_price",
  "high": "high_price"
}
```

**Treemap:**
```json
{
  "name": "Hierarchy",
  "id": "node_id",
  "parentId": "parent_id",
  "key": "node_name",
  "value": "size"
}
```

**Radar Chart:**
```json
{
  "name": "Metrics",
  "key": "category",
  "dimensions": ["metric1", "metric2", "metric3"]
}
```

**Map:**
```json
{
  "name": "Regional Data",
  "key": "country_name",
  "value": "metric"
}
```

---

## Example Generated Code

### Example 1: Bar Chart - Revenue by Region

**Input Data Model:**
```json
{
  "type": "bar_chart",
  "columns": [
    {"generated_column_name": "region", "source": "sales.region"},
    {"generated_column_name": "revenue", "source": "SUM(sales.amount)"}
  ],
  "series": [{"name": "Revenue", "key": "region", "value": "revenue"}],
  "group_by": ["region"]
}
```

**Generated Code:**
```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Query sales data
    df = ds_clients['Sales DB'].execute_query("""
        SELECT
            region,
            SUM(amount) as revenue
        FROM sales
        GROUP BY region
        ORDER BY revenue DESC
    """)

    print("df Info:", df.info())
    print("df head:", df.head())
    print("Final df Preview:", df.head())

    return df
```

### Example 2: Scatter Plot - Price vs Quantity

**Input Data Model:**
```json
{
  "type": "scatter_plot",
  "columns": [
    {"generated_column_name": "price", "source": "products.price"},
    {"generated_column_name": "quantity", "source": "sales.quantity_sold"}
  ],
  "series": [{"name": "Sales", "x": "price", "y": "quantity"}]
}
```

**Generated Code:**
```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Join products with sales
    query = """
        SELECT
            p.price,
            s.quantity_sold as quantity
        FROM products p
        INNER JOIN sales s ON p.product_id = s.product_id
        WHERE s.quantity_sold > 0
    """

    df = ds_clients['Sales DB'].execute_query(query)

    print("df Info:", df.info())
    print("df head:", df.head())
    print("Final df Preview:", df.head())

    return df
```

### Example 3: Combining Excel + Database

**Input Data Model:**
```json
{
  "type": "line_chart",
  "columns": [
    {"generated_column_name": "month", "source": "sales.month"},
    {"generated_column_name": "actual", "source": "sales.revenue"},
    {"generated_column_name": "budget", "source": "budget.xlsx"}
  ],
  "series": [
    {"name": "Actual", "key": "month", "value": "actual"},
    {"name": "Budget", "key": "month", "value": "budget"}
  ]
}
```

**Generated Code:**
```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Get actual sales from database
    sales_df = ds_clients['Sales DB'].execute_query("""
        SELECT
            DATE_TRUNC('month', sale_date) as month,
            SUM(amount) as actual
        FROM sales
        WHERE sale_date >= '2024-01-01'
        GROUP BY DATE_TRUNC('month', sale_date)
        ORDER BY month
    """)

    print("Sales df Info:", sales_df.info())
    print("Sales df head:", sales_df.head())

    # Read budget from Excel
    budget_df = pd.read_excel(
        excel_files[0].path,
        sheet_name=0
    )
    budget_df.columns = ['month', 'budget']
    budget_df['month'] = pd.to_datetime(budget_df['month'])

    print("Budget df Info:", budget_df.info())
    print("Budget df head:", budget_df.head())

    # Merge actual and budget
    df = pd.merge(
        sales_df,
        budget_df,
        on='month',
        how='left'
    )

    df = df.sort_values('month', ascending=True)

    print("df Preview:", df.head())
    print("Final df Preview:", df.head())

    return df
```

---

## Code Validation Prompt (Optional)

**Source**: `backend/app/ai/agents/coder/coder.py:260-298`

**Note**: Currently disabled (returns `{"valid": True}` always)

```python
You are a highly skilled data engineer and data scientist.

Your goal: Given a data model, content and a generated code, validate the code.

**Context and Inputs**:
- Data Model:
<data_model>
{data_model}
</data_model>

- Generated Code:
<generated_code>
{code}
</generated_code>

**Guidelines**:
1. There can be multiple dataframes as transformations steps
2. There should only be one final dataframe as output
3. Validate only read operations on the data sources. No insert/delete/add/update/put/drop.
4. Validate the code is close enough to the data model. It doesnt need to be exactly the same.
5. Do not be strict around code style.

Response format:
{
    "valid": true,
    "reasoning": "Reasoning for the failed validation" (if valid is false)
}

Now produce ONLY the JSON response as described. Do not output anything else besides the JSON response. No markdown, no comments, no triple backticks, no triple quotes, no triple anything, no text, no anything.
```

---

## Key Context Sections Explained

### 1. Instructions Context
Organization-specific business rules and conventions:
- Custom column naming conventions
- Specific aggregation rules
- Business logic requirements
- Preferred SQL patterns

**Example:**
```
- Always use fiscal year calculations (July 1 - June 30)
- Revenue should exclude returns
- Customer names must be title-cased
- Use ISO date formats (YYYY-MM-DD)
```

### 2. Mentions Context
Explicit references from user message:
```xml
<mentions>
@sales_table (id: uuid, type: table)
@Q4_analysis (id: uuid, type: widget)
@revenue_metric (id: uuid, type: instruction)
</mentions>
```

### 3. Entities Context
Business entity definitions:
```
Entity: Revenue
Definition: Sum of all closed deal amounts excluding refunds
Calculation: SUM(deals.amount) WHERE status='closed' AND type!='refund'

Entity: Customer Lifetime Value
Definition: Total revenue from a customer across all time
Calculation: SUM(transactions.amount) GROUP BY customer_id
```

### 4. Similar Code Snippets
Past successful/failed code for learning:

**Successful:**
```python
# Similar: bar_chart with grouping
def generate_df(ds_clients, excel_files):
    df = ds_clients['DB'].execute_query("""
        SELECT category, COUNT(*) as count
        FROM products
        GROUP BY category
        ORDER BY count DESC
        LIMIT 10
    """)
    return df
# Result: Success, 10 rows
```

**Failed:**
```python
# Similar: bar_chart with grouping
def generate_df(ds_clients, excel_files):
    df = ds_clients['DB'].execute_query("""
        SELECT categorie, COUNT(*) as count
        FROM products
        GROUP BY categorie
    """)
    return df
# Error: column "categorie" does not exist
# Hint: Check schema for correct column name
```

---

## Execution Flow

```
1. User: "Show revenue by region as bar chart"
        ↓
2. Planner: Generates data_model JSON
        ↓
3. Coder.data_model_to_code() called with:
   - data_model
   - schemas (database schemas)
   - ds_clients (available connections)
   - excel_files (uploaded files)
   - instructions_context (business rules)
   - previous attempts (if retrying)
        ↓
4. LLM receives full prompt with all context
        ↓
5. LLM generates: def generate_df(...)
        ↓
6. Code cleaned (remove markdown, truncate after return)
        ↓
7. Optional: Validator checks code (currently disabled)
        ↓
8. StreamingCodeExecutor.execute_code() runs it
        ↓
9. Returns DataFrame or raises exception
```

---

## Security & Constraints

### Enforced by Prompt (Not Code):
- ✅ Read-only operations only
- ✅ Use existing schema columns only
- ✅ No data modification (INSERT/UPDATE/DELETE/DROP)

### Not Enforced:
- ❌ No sandboxing (relies on DB user permissions)
- ❌ No query analysis (SQL injection possible if LLM compromised)
- ❌ No resource limits in prompt

### Best Practice:
Configure database users with **read-only permissions** to ensure safety.

---

## Key Files

**Coder Agent**: `backend/app/ai/agents/coder/coder.py:21-298`
**Data Model Schema**: `backend/app/ai/tools/schemas/create_data_model.py:1-119`
**Code Execution**: `backend/app/ai/code_execution/code_execution.py:1`
**Context Builders**: `backend/app/ai/context/builders/`

---

## Summary

The Coder agent receives:
- **Data model** (chart type + column mappings)
- **Schemas** (available tables/columns)
- **Context** (business rules, mentions, entities)
- **Error history** (if retrying)

And generates:
- **Python function** that queries data sources
- **Returns DataFrame** matching the data model
- **Includes debugging** print statements for transparency

The LLM is instructed to be resilient (reduce scope on errors), follow business rules strictly, and produce clean, executable code without markdown formatting.
