# Schemas in the Coder Agent

This document explains what "schemas" are in the Coder agent, how they're obtained, and what they look like.

**Source Files:**
- Schema Builder: `backend/app/ai/context/builders/schema_context_builder.py`
- Schema Rendering: `backend/app/ai/context/sections/tables_schema_section.py`
- Data Model: `backend/app/models/datasource_table.py`
- Formatters: `backend/app/ai/prompt_formatters.py`

---

## What Are Schemas?

**Schemas** are the **ground truth** about available database tables and columns that the Coder agent uses to generate correct SQL queries and DataFrame code.

They provide:
- ✅ Table names
- ✅ Column names and data types
- ✅ Primary keys (PKs)
- ✅ Foreign keys (FKs) - relationships between tables
- ✅ Usage statistics (how often used, success rate)
- ✅ User feedback (thumbs up/down)
- ✅ Structural metrics (centrality, richness, entity-likeness)
- ✅ Metadata (e.g., Tableau datasource info)

---

## How Schemas Are Obtained

### 1. Stored in Database

Schemas are **pre-indexed** and stored in the `datasource_tables` table:

```python
class DataSourceTable(BaseSchema):
    __tablename__ = 'datasource_tables'

    name = Column(String)                    # Table name (e.g., "sales")
    columns = Column(JSON)                   # [{"name": "id", "dtype": "INTEGER"}, ...]
    pks = Column(JSON)                       # Primary keys
    fks = Column(JSON)                       # Foreign keys
    no_rows = Column(Integer)                # Row count
    datasource_id = Column(String)           # Which data source

    is_active = Column(Boolean)              # Is table actively used?
    metadata_json = Column(JSON)             # Extra metadata (Tableau, dbt, etc.)

    # Structural metrics (computed during schema refresh)
    centrality_score = Column(Float)         # Graph centrality
    richness = Column(Float)                 # Column count/diversity
    degree_in = Column(Integer)              # Incoming FK count
    degree_out = Column(Integer)             # Outgoing FK count
    entity_like = Column(Boolean)            # Is this a core entity table?
```

**When Indexed:**
- When a data source is added/refreshed
- Via metadata indexing jobs
- From dbt models, Tableau datasources, or direct DB introspection

### 2. Built by SchemaContextBuilder

**Location:** `backend/app/ai/context/builders/schema_context_builder.py:31`

```python
class SchemaContextBuilder:
    async def build(
        self,
        include_inactive: bool = False,
        with_stats: bool = True,
        top_k: Optional[int] = None
    ) -> TablesSchemaContext:
        """
        Build schema context from report's data sources.

        Parameters:
        - include_inactive: Include tables marked as inactive
        - with_stats: Include usage/feedback statistics
        - top_k: Return only top K tables by score
        """
```

**Process:**

```
1. Get data sources from report (report.data_sources)
        ↓
2. For each data source:
   - Query DataSourceTable from database
   - Load TableStats (usage, success rate, feedback)
   - Check if user has overlays (user-specific access)
        ↓
3. For each table:
   - Extract columns, PKs, FKs
   - Calculate score based on usage, feedback, structure
   - Format as PromptTable object
        ↓
4. Sort by score (highest first)
        ↓
5. Optionally limit to top_k tables
        ↓
6. Render as XML-formatted string
```

### 3. Scoring Algorithm

**Location:** `backend/app/ai/context/builders/schema_context_builder.py:181`

Tables are ranked by a composite score:

```python
usage_signal = (weighted_usage_count)**0.5
feedback_signal = (weighted_pos_feedback - weighted_neg_feedback)
structural_signal = centrality_score + richness + (0.5 if entity_like else 0)
recency = e^(-age_days / 14)

score = 0.35 × (usage_signal × recency) +
        0.25 × success_rate +
        0.20 × feedback_signal +
        0.20 × structural_signal -
        0.20 × (failure_count)**0.5
```

**Weights:**
- **35%** - Usage (with recency decay)
- **25%** - Success rate (how reliable)
- **20%** - Feedback (user votes)
- **20%** - Structure (graph metrics)
- **-20%** - Failure penalty

**Why Score?** To show the LLM the **most relevant tables first** and optionally limit to top K.

### 4. Passed to Coder

**Location:** `backend/app/ai/tools/implementations/create_widget.py:255`

```python
context_view = runtime_ctx.get("context_view")
schemas_section = getattr(context_view.static, "schemas", None)
schemas = schemas_section.render() if schemas_section else ""

# Pass to coder
code = await coder.data_model_to_code(
    data_model=data_model,
    schemas=schemas,  # ← Formatted schema string
    ...
)
```

---

## Schema Format - XML Representation

**Location:** `backend/app/ai/context/sections/tables_schema_section.py:15`

Schemas are rendered as **XML** for structured representation:

```xml
<schemas>
  <data_source name="Sales DB" type="postgresql" id="uuid-123">
    <context>Production sales database with customer and order data</context>

    <table name="customers">
      <columns>
        <column name="customer_id" dtype="INTEGER"/>
        <column name="name" dtype="VARCHAR"/>
        <column name="email" dtype="VARCHAR"/>
        <column name="created_at" dtype="TIMESTAMP"/>
      </columns>
      <metrics>
        <score value="0.856"/>
        <usage count="120" success="115" failure="5"/>
        <success_rate value="0.958"/>
        <feedback pos="15" neg="2"/>
        <last_used_at value="2024-10-28T14:30:00Z"/>
      </metrics>
    </table>

    <table name="orders">
      <columns>
        <column name="order_id" dtype="INTEGER"/>
        <column name="customer_id" dtype="INTEGER"/>
        <column name="order_date" dtype="DATE"/>
        <column name="total_amount" dtype="DECIMAL"/>
        <column name="status" dtype="VARCHAR"/>
      </columns>
      <metrics>
        <score value="0.923"/>
        <usage count="250" success="245" failure="5"/>
        <success_rate value="0.98"/>
        <feedback pos="28" neg="1"/>
        <last_used_at value="2024-10-29T09:15:00Z"/>
      </metrics>
    </table>

    <table name="products">
      <columns>
        <column name="product_id" dtype="INTEGER"/>
        <column name="name" dtype="VARCHAR"/>
        <column name="price" dtype="DECIMAL"/>
        <column name="category" dtype="VARCHAR"/>
      </columns>
      <metrics>
        <score value="0.712"/>
        <usage count="85" success="82" failure="3"/>
        <success_rate value="0.965"/>
        <feedback pos="10" neg="0"/>
        <last_used_at value="2024-10-27T16:45:00Z"/>
      </metrics>
    </table>
  </data_source>

  <data_source name="Analytics DB" type="snowflake" id="uuid-456">
    <table name="page_views">
      <columns>
        <column name="session_id" dtype="VARCHAR"/>
        <column name="page_url" dtype="VARCHAR"/>
        <column name="viewed_at" dtype="TIMESTAMP"/>
        <column name="user_id" dtype="INTEGER"/>
      </columns>
      <metrics>
        <score value="0.634"/>
        <usage count="45" success="43" failure="2"/>
        <success_rate value="0.956"/>
        <feedback pos="5" neg="1"/>
      </metrics>
    </table>
  </data_source>
</schemas>
```

---

## Alternative Format - SQL-like (Legacy)

**Location:** `backend/app/ai/prompt_formatters.py:88`

There's also a `TableFormatter` that renders schemas as SQL CREATE TABLE statements:

```sql
CREATE TABLE customers (
    customer_id INTEGER,
    name VARCHAR,
    email VARCHAR,
    created_at TIMESTAMP,
    primary key (customer_id)
    -- metrics --
    score: 0.856
    usage: 120, success: 115, failure: 5
    success_rate: 0.958
    feedback: +15 / -2
    last_used: 2024-10-28T14:30:00Z
    structural: centrality=0.45, richness=0.82, degree_in=3, degree_out=2, entity_like=True
)

CREATE TABLE orders (
    order_id INTEGER,
    customer_id INTEGER,
    order_date DATE,
    total_amount DECIMAL,
    status VARCHAR,
    primary key (order_id),
    foreign key (customer_id) references customers(customer_id)
    -- metrics --
    score: 0.923
    usage: 250, success: 245, failure: 5
    success_rate: 0.98
    feedback: +28 / -1
    last_used: 2024-10-29T09:15:00Z
)
```

---

## Real Example - E-Commerce Database

### Database Structure

**PostgreSQL Database:**
```
sales_db
├── customers (10,000 rows)
│   ├── customer_id (PK)
│   ├── name
│   ├── email
│   └── created_at
├── orders (50,000 rows)
│   ├── order_id (PK)
│   ├── customer_id (FK → customers)
│   ├── order_date
│   ├── total_amount
│   └── status
├── order_items (200,000 rows)
│   ├── item_id (PK)
│   ├── order_id (FK → orders)
│   ├── product_id (FK → products)
│   ├── quantity
│   └── price
└── products (1,000 rows)
    ├── product_id (PK)
    ├── name
    ├── price
    └── category
```

### Stored in `datasource_tables` Table

```python
# customers table entry
{
    "id": "uuid-1",
    "name": "customers",
    "columns": [
        {"name": "customer_id", "dtype": "INTEGER"},
        {"name": "name", "dtype": "VARCHAR"},
        {"name": "email", "dtype": "VARCHAR"},
        {"name": "created_at", "dtype": "TIMESTAMP"}
    ],
    "pks": [{"name": "customer_id", "dtype": "INTEGER"}],
    "fks": [],
    "no_rows": 10000,
    "is_active": True,
    "centrality_score": 0.45,
    "richness": 0.25,
    "degree_in": 0,
    "degree_out": 1,  # Referenced by orders
    "entity_like": True
}

# orders table entry
{
    "id": "uuid-2",
    "name": "orders",
    "columns": [
        {"name": "order_id", "dtype": "INTEGER"},
        {"name": "customer_id", "dtype": "INTEGER"},
        {"name": "order_date", "dtype": "DATE"},
        {"name": "total_amount", "dtype": "DECIMAL"},
        {"name": "status", "dtype": "VARCHAR"}
    ],
    "pks": [{"name": "order_id", "dtype": "INTEGER"}],
    "fks": [
        {
            "column": {"name": "customer_id", "dtype": "INTEGER"},
            "references_name": "customers",
            "references_column": {"name": "customer_id", "dtype": "INTEGER"}
        }
    ],
    "no_rows": 50000,
    "is_active": True,
    "centrality_score": 0.85,  # High - connects many tables
    "richness": 0.5,
    "degree_in": 1,   # Referenced by order_items
    "degree_out": 2,  # References customers + used in aggregations
    "entity_like": True
}
```

### Rendered Schema (Passed to Coder)

```xml
<schemas>
  <data_source name="Sales DB" type="postgresql" id="uuid-sales-db">
    <context>E-commerce production database containing customer orders and product catalog</context>

    <table name="orders">
      <columns>
        <column name="order_id" dtype="INTEGER"/>
        <column name="customer_id" dtype="INTEGER"/>
        <column name="order_date" dtype="DATE"/>
        <column name="total_amount" dtype="DECIMAL"/>
        <column name="status" dtype="VARCHAR"/>
      </columns>
      <metrics>
        <score value="0.923"/>
        <usage count="250" success="245" failure="5"/>
        <success_rate value="0.98"/>
        <feedback pos="28" neg="1"/>
        <last_used_at value="2024-10-29T09:15:00Z"/>
      </metrics>
    </table>

    <table name="customers">
      <columns>
        <column name="customer_id" dtype="INTEGER"/>
        <column name="name" dtype="VARCHAR"/>
        <column name="email" dtype="VARCHAR"/>
        <column name="created_at" dtype="TIMESTAMP"/>
      </columns>
      <metrics>
        <score value="0.856"/>
        <usage count="120" success="115" failure="5"/>
        <success_rate value="0.958"/>
        <feedback pos="15" neg="2"/>
        <last_used_at value="2024-10-28T14:30:00Z"/>
      </metrics>
    </table>

    <table name="order_items">
      <columns>
        <column name="item_id" dtype="INTEGER"/>
        <column name="order_id" dtype="INTEGER"/>
        <column name="product_id" dtype="INTEGER"/>
        <column name="quantity" dtype="INTEGER"/>
        <column name="price" dtype="DECIMAL"/>
      </columns>
      <metrics>
        <score value="0.789"/>
        <usage count="95" success="92" failure="3"/>
        <success_rate value="0.968"/>
        <feedback pos="12" neg="1"/>
        <last_used_at value="2024-10-28T11:20:00Z"/>
      </metrics>
    </table>

    <table name="products">
      <columns>
        <column name="product_id" dtype="INTEGER"/>
        <column name="name" dtype="VARCHAR"/>
        <column name="price" dtype="DECIMAL"/>
        <column name="category" dtype="VARCHAR"/>
      </columns>
      <metrics>
        <score value="0.712"/>
        <usage count="85" success="82" failure="3"/>
        <success_rate value="0.965"/>
        <feedback pos="10" neg="0"/>
        <last_used_at value="2024-10-27T16:45:00Z"/>
      </metrics>
    </table>
  </data_source>
</schemas>
```

**Note**: Tables are sorted by score (highest first). In this example:
1. `orders` (0.923) - Most frequently used, highest success rate
2. `customers` (0.856) - Core entity, good usage
3. `order_items` (0.789) - Detail table, good performance
4. `products` (0.712) - Less frequently used but reliable

---

## How Coder Uses Schemas

### 1. Column Name Validation

When generating SQL, the LLM checks schemas for exact column names:

**User Prompt:** "Show revenue by region"

**LLM checks schemas:**
```xml
<table name="sales">
  <column name="region" dtype="VARCHAR"/>
  <column name="amount" dtype="DECIMAL"/>
</table>
```

**Generated SQL:**
```sql
SELECT region, SUM(amount) as revenue
FROM sales
GROUP BY region
```

**If LLM tried wrong column name** (e.g., "region_name"):
```python
# Error on execution:
# psycopg2.errors.UndefinedColumn: column "region_name" does not exist
# HINT: Did you mean: region

# On retry, LLM sees the error and fixes it
```

### 2. Table Selection

High-scored tables are prioritized:

**Prompt:** "Show customer orders"

**LLM sees:**
- `orders` (score: 0.923) ✅ High usage, high success
- `order_archive` (score: 0.12) ❌ Low usage, might be inactive

**LLM chooses:** `orders` table

### 3. Join Detection

Foreign keys guide JOIN queries:

**Prompt:** "Show orders with customer names"

**LLM sees:**
```xml
<table name="orders">
  <column name="customer_id" dtype="INTEGER"/>
  <!-- FK relationship indicated in metrics or explicit FK tags -->
</table>
<table name="customers">
  <column name="customer_id" dtype="INTEGER"/>
  <column name="name" dtype="VARCHAR"/>
</table>
```

**Generated SQL:**
```sql
SELECT
    o.order_id,
    o.order_date,
    c.name as customer_name
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
```

### 4. Type-Aware Operations

Data types inform aggregations and operations:

**Prompt:** "Show average order amount"

**LLM sees:**
```xml
<column name="total_amount" dtype="DECIMAL"/>
```

**Generated code:**
```python
df = ds_clients['Sales DB'].execute_query("""
    SELECT AVG(total_amount) as avg_amount
    FROM orders
""")
```

If it was `VARCHAR`, the LLM would cast or avoid aggregation.

---

## Advanced Features

### 1. Top-K Filtering

Limit schemas to most relevant tables:

```python
schema_builder = SchemaContextBuilder(db, data_sources, org, report)
schema_context = await schema_builder.build(
    with_stats=True,
    top_k=10  # Only top 10 tables by score
)
```

**Why?** Reduce token usage for large databases (100+ tables).

### 2. User-Specific Overlays

For data sources with `auth_policy='user_required'`:

```python
# User A sees:
<table name="sales">
  <column name="region" dtype="VARCHAR"/>
  <column name="amount" dtype="DECIMAL"/>
</table>

# User B (with restricted access) sees:
<table name="sales">
  <column name="region" dtype="VARCHAR"/>
  <column name="amount_bucket" dtype="VARCHAR"/>  <!-- Anonymized -->
</table>
```

Stored in `user_data_source_table` and `user_data_source_column` tables.

### 3. Metadata Integration

**Tableau Datasources:**
```xml
<table name="sales_dashboard_v2">
  <metadata datasourceLuid="abc-123" projectName="Finance" name="Sales Analysis"/>
  <columns>
    <column name="region" dtype="VARCHAR"/>
    ...
  </columns>
</table>
```

**dbt Models:**
```xml
<table name="fct_orders">
  <metadata dbt_model="fct_orders" dbt_schema="analytics"/>
  <columns>
    <column name="order_key" dtype="INTEGER"/>
    ...
  </columns>
</table>
```

---

## Schema Refresh & Indexing

**When schemas are updated:**

1. **Manual Refresh** - User triggers data source refresh
2. **Scheduled Jobs** - Metadata indexing jobs (daily/weekly)
3. **dbt Integration** - Import from dbt project manifest
4. **Tableau Sync** - Pull from Tableau server metadata API

**Process:**
```
1. Connect to data source
2. Introspect database schema (INFORMATION_SCHEMA)
3. Detect primary keys, foreign keys
4. Calculate structural metrics (centrality, richness)
5. Store in datasource_tables table
6. Compute table statistics from usage events
```

---

## Key Takeaways

1. **Schemas = Ground Truth** - Prevent hallucinated column names
2. **XML Format** - Structured, parseable by LLM
3. **Scored & Ranked** - Most relevant tables shown first
4. **Usage-Driven** - Tables with high success rates prioritized
5. **Multi-Source** - Can include multiple databases in one prompt
6. **Metadata-Rich** - Includes usage stats, feedback, structural metrics
7. **User-Aware** - Respects access controls via overlays
8. **Live Context** - Built fresh for each agent execution

Schemas ensure the Coder agent generates **valid, executable SQL** by providing accurate information about available tables and columns, rather than guessing or hallucinating schema details.
