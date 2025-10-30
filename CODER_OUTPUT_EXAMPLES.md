# Coder Output Examples

Real examples of what the Coder agent generates and what those outputs produce.

---

## Example 1: Bar Chart - Revenue by Region

### Input

**User Prompt**: "Show me revenue by region"

**Data Model**:
```json
{
  "type": "bar_chart",
  "columns": [
    {
      "generated_column_name": "region",
      "source": "sales.region",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "revenue",
      "source": "SUM(sales.amount)",
      "source_data_source_id": "uuid-123"
    }
  ],
  "series": [
    {"name": "Revenue", "key": "region", "value": "revenue"}
  ],
  "group_by": ["region"]
}
```

**Available Schema**:
```xml
<data_source name="Sales DB" type="postgresql">
  <table name="sales">
    <column name="region" dtype="VARCHAR"/>
    <column name="amount" dtype="DECIMAL"/>
    <column name="sale_date" dtype="DATE"/>
  </table>
</data_source>
```

### Coder Output (Generated Code)

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Query sales data and aggregate by region
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

### Execution Output (DataFrame)

```python
     region  revenue
0      East   180000
1     North   150000
2     South   120000
3      West    95000
```

### Console Output (from print statements)

```
df Info: <class 'pandas.core.frame.DataFrame'>
RangeIndex: 4 entries, 0 to 3
Data columns (total 2 columns):
 #   Column   Non-Null Count  Dtype
---  ------   --------------  -----
 0   region   4 non-null      object
 1   revenue  4 non-null      float64
dtypes: float64(1), object(1)
memory usage: 192.0+ bytes

df head:      region  revenue
0      East   180000
1     North   150000
2     South   120000
3      West    95000

Final df Preview:      region  revenue
0      East   180000
1     North   150000
2     South   120000
3      West    95000
```

---

## Example 2: Line Chart - Monthly Sales Trend

### Input

**User Prompt**: "Show monthly sales trend for 2024"

**Data Model**:
```json
{
  "type": "line_chart",
  "columns": [
    {
      "generated_column_name": "month",
      "source": "DATE_TRUNC('month', sales.sale_date)",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "total_sales",
      "source": "SUM(sales.amount)",
      "source_data_source_id": "uuid-123"
    }
  ],
  "series": [
    {"name": "Sales", "key": "month", "value": "total_sales"}
  ],
  "group_by": ["month"]
}
```

### Coder Output

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Query monthly sales data
    df = ds_clients['Sales DB'].execute_query("""
        SELECT
            DATE_TRUNC('month', sale_date) as month,
            SUM(amount) as total_sales
        FROM sales
        WHERE sale_date >= '2024-01-01'
          AND sale_date < '2025-01-01'
        GROUP BY DATE_TRUNC('month', sale_date)
        ORDER BY month ASC
    """)

    print("df Info:", df.info())
    print("df head:", df.head())
    print("Final df Preview:", df.head())

    return df
```

### Execution Output

```python
        month  total_sales
0  2024-01-01       450000
1  2024-02-01       520000
2  2024-03-01       480000
3  2024-04-01       550000
4  2024-05-01       590000
5  2024-06-01       610000
6  2024-07-01       580000
7  2024-08-01       620000
8  2024-09-01       650000
9  2024-10-01       670000
```

---

## Example 3: Pie Chart - Product Category Distribution

### Input

**User Prompt**: "Show sales distribution by product category"

**Data Model**:
```json
{
  "type": "pie_chart",
  "columns": [
    {
      "generated_column_name": "category",
      "source": "products.category",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "total_amount",
      "source": "SUM(sales.amount)",
      "source_data_source_id": "uuid-123"
    }
  ],
  "series": [
    {"name": "Sales", "key": "category", "value": "total_amount"}
  ],
  "group_by": ["category"]
}
```

### Coder Output

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Join products and sales to get category distribution
    df = ds_clients['Sales DB'].execute_query("""
        SELECT
            p.category,
            SUM(s.amount) as total_amount
        FROM sales s
        INNER JOIN products p ON s.product_id = p.product_id
        GROUP BY p.category
        ORDER BY total_amount DESC
    """)

    print("df Info:", df.info())
    print("df head:", df.head())
    print("Final df Preview:", df.head())

    return df
```

### Execution Output

```python
      category  total_amount
0  Electronics        850000
1    Furniture        620000
2     Clothing        540000
3        Books        230000
4         Toys        180000
```

---

## Example 4: Scatter Plot - Price vs Sales

### Input

**User Prompt**: "Show relationship between price and sales quantity"

**Data Model**:
```json
{
  "type": "scatter_plot",
  "columns": [
    {
      "generated_column_name": "price",
      "source": "products.price",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "quantity_sold",
      "source": "SUM(sales.quantity)",
      "source_data_source_id": "uuid-123"
    }
  ],
  "series": [
    {"name": "Price vs Quantity", "x": "price", "y": "quantity_sold"}
  ],
  "group_by": ["price"]
}
```

### Coder Output

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Analyze price vs quantity relationship
    df = ds_clients['Sales DB'].execute_query("""
        SELECT
            p.price,
            SUM(s.quantity) as quantity_sold
        FROM sales s
        INNER JOIN products p ON s.product_id = p.product_id
        GROUP BY p.price
        ORDER BY p.price ASC
    """)

    print("df Info:", df.info())
    print("df head:", df.head())
    print("Final df Preview:", df.head())

    return df
```

### Execution Output

```python
    price  quantity_sold
0    9.99           1200
1   19.99            980
2   29.99            750
3   39.99            620
4   49.99            480
5   59.99            320
6   79.99            210
7   99.99            150
```

---

## Example 5: Combining Database + Excel

### Input

**User Prompt**: "Compare actual sales to budget by region"

**Data Model**:
```json
{
  "type": "bar_chart",
  "columns": [
    {
      "generated_column_name": "region",
      "source": "sales.region",
      "source_data_source_id": "uuid-db-123"
    },
    {
      "generated_column_name": "actual",
      "source": "SUM(sales.amount)",
      "source_data_source_id": "uuid-db-123"
    },
    {
      "generated_column_name": "budget",
      "source": "budget.xlsx",
      "source_data_source_id": "uuid-file-456"
    }
  ],
  "series": [
    {"name": "Actual", "key": "region", "value": "actual"},
    {"name": "Budget", "key": "region", "value": "budget"}
  ],
  "group_by": ["region"]
}
```

**Excel File** (`budget.xlsx`):
```
     A          B
1  Region   Budget
2  North    140000
3  South    130000
4  East     170000
5  West     100000
```

### Coder Output

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Get actual sales from database
    actual_df = ds_clients['Sales DB'].execute_query("""
        SELECT
            region,
            SUM(amount) as actual
        FROM sales
        WHERE sale_date >= '2024-01-01'
        GROUP BY region
    """)

    print("Actual df Info:", actual_df.info())
    print("Actual df head:", actual_df.head())

    # Read budget from Excel
    budget_df = pd.read_excel(
        excel_files[0].path,
        sheet_name=0,
        header=0
    )
    budget_df.columns = ['region', 'budget']

    print("Budget df Info:", budget_df.info())
    print("Budget df head:", budget_df.head())

    # Merge actual and budget
    df = pd.merge(
        actual_df,
        budget_df,
        on='region',
        how='outer'
    )

    # Sort by region
    df = df.sort_values('region')

    print("df Preview:", df.head())
    print("Final df Preview:", df.head())

    return df
```

### Execution Output

```python
   region  actual  budget
0    East  180000  170000
1   North  150000  140000
2   South  120000  130000
3    West   95000  100000
```

### Console Output

```
Actual df Info: <class 'pandas.core.frame.DataFrame'>
RangeIndex: 4 entries, 0 to 3
Data columns (total 2 columns):
 #   Column   Non-Null Count  Dtype
---  ------   --------------  -----
 0   region   4 non-null      object
 1   actual   4 non-null      float64
dtypes: float64(1), object(1)

Actual df head:    region  actual
0    East  180000
1   North  150000
2   South  120000
3    West   95000

Budget df Info: <class 'pandas.core.frame.DataFrame'>
RangeIndex: 4 entries, 0 to 3
Data columns (total 2 columns):
 #   Column   Non-Null Count  Dtype
---  ------   --------------  -----
 0   region   4 non-null      object
 1   budget   4 non-null      int64
dtypes: int64(1), object(1)

Budget df head:    region  budget
0   North  140000
1   South  130000
2    East  170000
3    West  100000

df Preview:    region  actual  budget
0    East  180000  170000
1   North  150000  140000
2   South  120000  130000
3    West   95000  100000

Final df Preview:    region  actual  budget
0    East  180000  170000
1   North  150000  140000
2   South  120000  130000
3    West   95000  100000
```

---

## Example 6: Heatmap - Sales by Month and Product

### Input

**User Prompt**: "Show sales heatmap by month and product category"

**Data Model**:
```json
{
  "type": "heatmap",
  "columns": [
    {
      "generated_column_name": "month",
      "source": "DATE_TRUNC('month', sales.sale_date)",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "category",
      "source": "products.category",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "sales",
      "source": "SUM(sales.amount)",
      "source_data_source_id": "uuid-123"
    }
  ],
  "series": [
    {"name": "Sales", "x": "month", "y": "category", "value": "sales"}
  ],
  "group_by": ["month", "category"]
}
```

### Coder Output

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Get sales by month and category
    df = ds_clients['Sales DB'].execute_query("""
        SELECT
            DATE_TRUNC('month', s.sale_date) as month,
            p.category,
            SUM(s.amount) as sales
        FROM sales s
        INNER JOIN products p ON s.product_id = p.product_id
        WHERE s.sale_date >= '2024-01-01'
        GROUP BY DATE_TRUNC('month', s.sale_date), p.category
        ORDER BY month ASC, category ASC
    """)

    print("df Info:", df.info())
    print("df head:", df.head())
    print("Final df Preview:", df.head())

    return df
```

### Execution Output

```python
         month     category  sales
0   2024-01-01     Clothing  45000
1   2024-01-01  Electronics  85000
2   2024-01-01    Furniture  62000
3   2024-02-01     Clothing  48000
4   2024-02-01  Electronics  92000
5   2024-02-01    Furniture  58000
6   2024-03-01     Clothing  52000
7   2024-03-01  Electronics  88000
8   2024-03-01    Furniture  65000
...
```

---

## Example 7: Table with Complex Aggregation

### Input

**User Prompt**: "Show customer summary with total orders, total spent, and average order value"

**Data Model**:
```json
{
  "type": "table",
  "columns": [
    {
      "generated_column_name": "customer_name",
      "source": "customers.name",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "total_orders",
      "source": "COUNT(DISTINCT orders.order_id)",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "total_spent",
      "source": "SUM(orders.total_amount)",
      "source_data_source_id": "uuid-123"
    },
    {
      "generated_column_name": "avg_order_value",
      "source": "AVG(orders.total_amount)",
      "source_data_source_id": "uuid-123"
    }
  ],
  "group_by": ["customer_name"],
  "limit": 10
}
```

### Coder Output

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Get customer summary statistics
    df = ds_clients['Sales DB'].execute_query("""
        SELECT
            c.name as customer_name,
            COUNT(DISTINCT o.order_id) as total_orders,
            SUM(o.total_amount) as total_spent,
            AVG(o.total_amount) as avg_order_value
        FROM customers c
        INNER JOIN orders o ON c.customer_id = o.customer_id
        GROUP BY c.name
        ORDER BY total_spent DESC
        LIMIT 10
    """)

    print("df Info:", df.info())
    print("df head:", df.head())
    print("Final df Preview:", df.head())

    return df
```

### Execution Output

```python
     customer_name  total_orders  total_spent  avg_order_value
0     Acme Corp            24       125000         5208.33
1  Global Solutions       18        98000         5444.44
2  TechStart Inc          15        87000         5800.00
3  Innovation Hub         21        82000         3904.76
4  Enterprise Co          12        75000         6250.00
5  NextGen LLC            19        72000         3789.47
6  Digital Systems        14        68000         4857.14
7  Future Tech            16        65000         4062.50
8  Smart Solutions        13        61000         4692.31
9  CloudWorks             11        58000         5272.73
```

---

## Example 8: Error and Retry

### Input

**User Prompt**: "Show revenue by region"

**First Attempt** (with error):

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Query sales data
    df = ds_clients['Sales DB'].execute_query("""
        SELECT
            region_name,  -- ERROR: Column doesn't exist
            SUM(amount) as revenue
        FROM sales
        GROUP BY region_name
    """)

    return df
```

**Error**:
```
psycopg2.errors.UndefinedColumn: column "region_name" does not exist
HINT: Did you mean: region?
```

### Second Attempt (after seeing error):

```python
def generate_df(ds_clients, excel_files):
    import pandas as pd

    # Query sales data - fixed column name
    df = ds_clients['Sales DB'].execute_query("""
        SELECT
            region,  -- FIXED: Used correct column name
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

**Success**:
```python
     region  revenue
0      East   180000
1     North   150000
2     South   120000
3      West    95000
```

---

## Key Characteristics of Coder Output

### 1. Function Signature
Always: `def generate_df(ds_clients, excel_files):`

### 2. Imports
Always imports: `import pandas as pd`

### 3. Print Statements (for debugging)
- `print("df Info:", df.info())` - Shows schema
- `print("df head:", df.head())` - Shows sample data
- `print("Final df Preview:", df.head())` - Final check

### 4. Data Source Access
- Database: `ds_clients['DB Name'].execute_query("SQL")`
- Excel: `pd.read_excel(excel_files[INDEX].path, ...)`

### 5. Return Statement
Always ends with: `return df`

### 6. Code Structure
1. Query/read data
2. Print debug info
3. Transform/merge if needed
4. Print intermediate results
5. Final transformations (sort, filter)
6. Print final result
7. Return DataFrame

---

## Output Format

**Coder Returns**: String containing Python code
**Execution Produces**: pandas DataFrame
**Stored**: Both code and data stored in Step model

**Complete Flow**:
```
Coder.data_model_to_code()
    ↓ returns string
Generated Python Code
    ↓ executed by
StreamingCodeExecutor.execute_code()
    ↓ returns tuple
(DataFrame, execution_log)
    ↓
Widget data created with:
{
  "columns": [...],
  "rows": [...],
  "info": {row_count, execution_time}
}
```

---

## Summary

The Coder outputs **pure Python code** that:
- ✅ Queries databases via `ds_clients`
- ✅ Reads Excel files via `pd.read_excel()`
- ✅ Transforms data with pandas
- ✅ Returns a DataFrame matching the data model
- ✅ Includes print statements for visibility
- ✅ Handles errors gracefully with retries

The execution of this code produces a **pandas DataFrame** that matches the structure specified in the data model, ready for visualization on the frontend!
