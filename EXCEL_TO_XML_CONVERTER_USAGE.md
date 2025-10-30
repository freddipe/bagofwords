# Excel Schema to XML Converter - Usage Guide

**Location**: `backend/app/ai/converters/excel_schema_to_xml.py`

Standalone converter for transforming Excel schema JSON into XML format for AI prompts.

---

## Installation

The converter is located at:
```
backend/app/ai/converters/
├── __init__.py
└── excel_schema_to_xml.py
```

Import with:
```python
from app.ai.converters import ExcelSchemaToXmlConverter, ExcelFileSchema
# or
from app.ai.converters import convert_excel_schemas_to_xml
```

---

## Quick Start

### Method 1: Using the Class

```python
from app.ai.converters import ExcelSchemaToXmlConverter, ExcelFileSchema

# Create file schema objects
files = [
    ExcelFileSchema(
        id="uuid-789",
        filename="budget_2024.xlsx",
        path="/uploads/budget_2024.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        sheet_schemas=[
            {
                "sheet_name": "Q4_Budget",
                "sheet_index": 0,
                "schema": {
                    "fields": {
                        "region": {"type": "string", "range": "A2:A5"},
                        "budget": {"type": "int", "range": "B2:B5"}
                    }
                }
            }
        ]
    )
]

# Convert to XML
converter = ExcelSchemaToXmlConverter()
xml_output = converter.convert_files(files)
print(xml_output)
```

### Method 2: Using Standalone Function

```python
from app.ai.converters import convert_excel_schemas_to_xml, ExcelFileSchema

files = [ExcelFileSchema(...)]  # Same as above
xml_output = convert_excel_schemas_to_xml(files)
```

### Method 3: Single File Conversion

```python
from app.ai.converters import convert_single_excel_schema_to_xml, ExcelFileSchema

file = ExcelFileSchema(...)  # Single file
xml_output = convert_single_excel_schema_to_xml(file)
```

---

## Output Example

### Input

```python
ExcelFileSchema(
    id="uuid-789",
    filename="budget_2024.xlsx",
    path="/uploads/budget_2024.xlsx",
    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    sheet_schemas=[
        {
            "sheet_name": "Q4_Budget",
            "sheet_index": 0,
            "schema": {
                "fields": {
                    "region": {"type": "string", "range": "A2:A5"},
                    "budget": {"type": "int", "range": "B2:B5"},
                    "oct": {"type": "int", "range": "C2:C5"}
                }
            }
        }
    ]
)
```

### Output

```xml
<files>
  <file id="uuid-789" filename="budget_2024.xlsx" path="/uploads/budget_2024.xlsx" content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet">
    <schema>File: budget_2024.xlsx
Path: /uploads/budget_2024.xlsx

Sheet Schemas:
Sheet Name: Q4_Budget
Sheet index: 0
{&#39;fields&#39;: {&#39;region&#39;: {&#39;type&#39;: &#39;string&#39;, &#39;range&#39;: &#39;A2:A5&#39;}, &#39;budget&#39;: {&#39;type&#39;: &#39;int&#39;, &#39;range&#39;: &#39;B2:B5&#39;}, &#39;oct&#39;: {&#39;type&#39;: &#39;int&#39;, &#39;range&#39;: &#39;C2:C5&#39;}}}

</schema>
  </file>
</files>
```

---

## Converting from SQLAlchemy Models

If you have SQLAlchemy `File` and `SheetSchema` models, convert them first:

```python
from app.ai.converters import ExcelSchemaToXmlConverter, ExcelFileSchema
from app.models.file import File

def convert_file_model_to_schema(file: File) -> ExcelFileSchema:
    """Convert SQLAlchemy File model to ExcelFileSchema dataclass."""
    sheet_schemas = []

    for sheet in file.sheet_schemas:
        sheet_schemas.append({
            "sheet_name": sheet.sheet_name,
            "sheet_index": sheet.sheet_index,
            "schema": sheet.schema  # Already a dict/JSON
        })

    return ExcelFileSchema(
        id=str(file.id),
        filename=file.filename,
        path=file.path,
        content_type=file.content_type,
        sheet_schemas=sheet_schemas
    )

# Usage
file_models = [...]  # List of File objects from database
file_schemas = [convert_file_model_to_schema(f) for f in file_models]

converter = ExcelSchemaToXmlConverter()
xml = converter.convert_files(file_schemas)
```

---

## Integration with Existing Code

### Replace FilesContextBuilder

**Before** (using existing code):
```python
from app.ai.context.builders.files_context_builder import FilesContextBuilder

builder = FilesContextBuilder(db, organization, report)
files_context = await builder.build()
xml = files_context.render()
```

**After** (using standalone converter):
```python
from app.ai.converters import ExcelSchemaToXmlConverter, ExcelFileSchema

# Convert File models to ExcelFileSchema
file_schemas = [
    ExcelFileSchema(
        id=str(f.id),
        filename=f.filename,
        path=f.path,
        content_type=f.content_type,
        sheet_schemas=[
            {
                "sheet_name": s.sheet_name,
                "sheet_index": s.sheet_index,
                "schema": s.schema
            }
            for s in f.sheet_schemas
        ]
    )
    for f in report.files
    if f.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
]

# Convert to XML
converter = ExcelSchemaToXmlConverter()
xml = converter.convert_files(file_schemas)
```

---

## API Reference

### ExcelFileSchema (Dataclass)

```python
@dataclass
class ExcelFileSchema:
    id: str                           # File UUID
    filename: str                     # e.g., "budget_2024.xlsx"
    path: str                         # e.g., "/uploads/budget_2024.xlsx"
    content_type: str                 # MIME type
    sheet_schemas: List[Dict[str, Any]]  # List of sheet schema JSON objects
```

### ExcelSchemaToXmlConverter (Class)

#### Methods

**`convert_files(files: List[ExcelFileSchema]) -> str`**
- Converts multiple files to XML
- Returns: XML string wrapped in `<files>` tag

**`convert_file(file: ExcelFileSchema) -> str`**
- Converts a single file to XML
- Returns: XML string for a single `<file>` element

**`_build_schema_content(file: ExcelFileSchema) -> str`** (private)
- Builds human-readable schema content
- Returns: Formatted string

**`_xml_escape(value: str) -> str`** (private)
- Escapes XML special characters
- Returns: Safe XML string

**`_xml_tag(name: str, inner: str, attrs: Optional[Dict]) -> str`** (private)
- Builds XML tag with attributes
- Returns: Complete XML tag

### Standalone Functions

**`convert_excel_schemas_to_xml(files: List[ExcelFileSchema]) -> str`**
- Convenience function for quick conversion
- Returns: XML string

**`convert_single_excel_schema_to_xml(file: ExcelFileSchema) -> str`**
- Converts single file
- Returns: XML string for one `<file>` element

---

## Advanced Usage

### Custom Schema Formatting

Subclass the converter to customize formatting:

```python
from app.ai.converters import ExcelSchemaToXmlConverter

class CustomExcelConverter(ExcelSchemaToXmlConverter):
    def _build_schema_content(self, file: ExcelFileSchema) -> str:
        """Custom formatting with JSON pretty-print."""
        import json

        lines = [
            f"File: {file.filename}",
            f"Path: {file.path}",
            "",
            "Sheet Schemas:"
        ]

        for sheet_schema in file.sheet_schemas:
            lines.append(f"Sheet Name: {sheet_schema.get('sheet_name')}")
            lines.append(f"Sheet Index: {sheet_schema.get('sheet_index')}")

            # Pretty-print JSON
            if 'schema' in sheet_schema:
                pretty_json = json.dumps(sheet_schema['schema'], indent=2)
                lines.append(pretty_json)

            lines.append("")

        return "\n".join(lines)

# Usage
converter = CustomExcelConverter()
xml = converter.convert_files(files)
```

### Filtering Files

Only convert Excel files:

```python
from app.ai.converters import convert_excel_schemas_to_xml, ExcelFileSchema

# Filter only Excel files
excel_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
excel_files = [
    f for f in all_files
    if f.content_type == excel_mime
]

xml = convert_excel_schemas_to_xml(excel_files)
```

### Multiple Sheets Example

```python
file = ExcelFileSchema(
    id="uuid-123",
    filename="financial_report.xlsx",
    path="/uploads/financial_report.xlsx",
    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    sheet_schemas=[
        {
            "sheet_name": "Revenue",
            "sheet_index": 0,
            "schema": {"fields": {...}}
        },
        {
            "sheet_name": "Expenses",
            "sheet_index": 1,
            "schema": {"fields": {...}}
        },
        {
            "sheet_name": "Profit",
            "sheet_index": 2,
            "schema": {"fields": {...}}
        }
    ]
)

converter = ExcelSchemaToXmlConverter()
xml = converter.convert_files([file])
# Output includes all 3 sheets in one <file> tag
```

---

## Testing

### Run Example

```bash
cd backend
python -m app.ai.converters.excel_schema_to_xml
```

### Unit Test Example

```python
import pytest
from app.ai.converters import ExcelSchemaToXmlConverter, ExcelFileSchema

def test_convert_single_file():
    file = ExcelFileSchema(
        id="test-123",
        filename="test.xlsx",
        path="/test/test.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        sheet_schemas=[
            {
                "sheet_name": "Sheet1",
                "sheet_index": 0,
                "schema": {"fields": {"col1": {"type": "string"}}}
            }
        ]
    )

    converter = ExcelSchemaToXmlConverter()
    xml = converter.convert_files([file])

    assert '<files>' in xml
    assert '<file id="test-123"' in xml
    assert '<schema>' in xml
    assert 'test.xlsx' in xml
```

---

## Benefits

1. **Standalone** - No dependencies on SQLAlchemy models or context builders
2. **Reusable** - Can be used anywhere, not tied to specific workflow
3. **Testable** - Easy to unit test with simple dataclasses
4. **Flexible** - Both class and function interfaces
5. **Extensible** - Can subclass for custom formatting
6. **Type-Safe** - Uses dataclasses with type hints
7. **Clear Separation** - Logic isolated from database/ORM layer

---

## Key Differences from Original Code

| Aspect | Original | Extracted |
|--------|----------|-----------|
| **Location** | Spread across 3 files | Single file |
| **Dependencies** | SQLAlchemy models | Simple dataclass |
| **Testability** | Requires DB setup | Pure functions |
| **Reusability** | Tied to context builder | Standalone |
| **Interface** | Only class method | Class + functions |

---

## Migration Path

1. **Phase 1**: Use new converter alongside existing code
2. **Phase 2**: Update FilesContextBuilder to use converter internally
3. **Phase 3**: Deprecate old implementation

Example Phase 2:

```python
# In files_context_builder.py
from app.ai.converters import convert_excel_schemas_to_xml, ExcelFileSchema

class FilesContextBuilder:
    async def build(self) -> FilesSchemaContext:
        files = self.report.files

        # Convert to ExcelFileSchema
        file_schemas = [...]

        # Use new converter
        xml = convert_excel_schemas_to_xml(file_schemas)

        # Return wrapped in FilesSchemaContext for compatibility
        return FilesSchemaContext.from_xml(xml)
```

---

## Summary

The extracted converter provides:
- ✅ Clean separation of concerns
- ✅ Easy testing without database
- ✅ Reusable across different contexts
- ✅ Both class and function interfaces
- ✅ Type-safe with dataclasses
- ✅ No SQLAlchemy dependencies

Use it anywhere you need to convert Excel schemas to XML for AI prompts!
