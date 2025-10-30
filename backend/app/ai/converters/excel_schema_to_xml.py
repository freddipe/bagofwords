"""
Excel Schema to XML Converter

Standalone converter that transforms Excel schema JSON into XML format
for use in AI prompts.

Usage:
    converter = ExcelSchemaToXmlConverter()
    xml_output = converter.convert_files(files)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ExcelFileSchema:
    """Data class representing an Excel file with its schema."""
    id: str
    filename: str
    path: str
    content_type: str
    sheet_schemas: List[Dict[str, Any]]  # List of SheetSchema JSON objects


class ExcelSchemaToXmlConverter:
    """
    Converts Excel file schemas from JSON to XML format.

    This class handles the transformation of database-stored Excel schemas
    into XML format suitable for LLM prompts.
    """

    def __init__(self):
        pass

    def convert_files(self, files: List[ExcelFileSchema]) -> str:
        """
        Convert a list of Excel files with schemas to XML format.

        Args:
            files: List of ExcelFileSchema objects

        Returns:
            XML string wrapped in <files> tag

        Example:
            >>> converter = ExcelSchemaToXmlConverter()
            >>> files = [ExcelFileSchema(...)]
            >>> xml = converter.convert_files(files)
            >>> print(xml)
            <files>
              <file filename="budget.xlsx" ...>
                <schema>...</schema>
              </file>
            </files>
        """
        file_nodes = []

        for file in files:
            file_xml = self.convert_file(file)
            file_nodes.append(file_xml)

        return self._xml_tag("files", "\n\n".join(file_nodes))

    def convert_file(self, file: ExcelFileSchema) -> str:
        """
        Convert a single Excel file schema to XML.

        Args:
            file: ExcelFileSchema object

        Returns:
            XML string for a single <file> element
        """
        # Build the schema content
        schema_content = self._build_schema_content(file)

        # Wrap in <schema> tag
        inner = self._xml_tag("schema", self._xml_escape(schema_content))

        # Create <file> tag with attributes
        return self._xml_tag(
            "file",
            inner,
            {
                "id": file.id,
                "filename": file.filename,
                "path": file.path,
                "content_type": file.content_type,
            }
        )

    def _build_schema_content(self, file: ExcelFileSchema) -> str:
        """
        Build the human-readable schema content string.

        Args:
            file: ExcelFileSchema object

        Returns:
            Formatted string describing the file and its sheets
        """
        lines = [
            f"File: {file.filename}",
            f"Path: {file.path}",
            "",
            "Sheet Schemas:"
        ]

        for sheet_schema in file.sheet_schemas:
            lines.append(f"Sheet Name: {sheet_schema.get('sheet_name', 'Unknown')}")
            lines.append(f"Sheet index: {sheet_schema.get('sheet_index', 0)}")

            # Include the schema JSON
            if 'schema' in sheet_schema:
                lines.append(str(sheet_schema['schema']))

            lines.append("")  # Empty line between sheets

        return "\n".join(lines)

    def _xml_escape(self, value: str) -> str:
        """
        Escape special XML characters.

        Args:
            value: String to escape

        Returns:
            Escaped string safe for XML content
        """
        if not value:
            return ""
        return (
            value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("'", "&#39;")
            .replace('"', "&quot;")
        )

    def _xml_tag(
        self,
        name: str,
        inner: str,
        attrs: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build an XML tag with optional attributes.

        Args:
            name: Tag name (e.g., "file", "schema")
            inner: Inner content of the tag
            attrs: Optional dictionary of attributes

        Returns:
            Complete XML tag string

        Example:
            >>> _xml_tag("file", "content", {"id": "123", "name": "test"})
            '<file id="123" name="test">\ncontent\n</file>'
        """
        attrs_str = ""
        if attrs:
            attrs_str = "".join(
                f' {k}="{self._xml_escape(str(v))}"'
                for k, v in attrs.items()
            )

        return f"<{name}{attrs_str}>\n{inner}\n</{name}>"


# Standalone function version
def convert_excel_schemas_to_xml(files: List[ExcelFileSchema]) -> str:
    """
    Standalone function to convert Excel schemas to XML.

    This is a convenience function that creates a converter instance
    and performs the conversion in one call.

    Args:
        files: List of ExcelFileSchema objects

    Returns:
        XML string

    Example:
        >>> files = [ExcelFileSchema(
        ...     id="uuid-123",
        ...     filename="budget.xlsx",
        ...     path="/uploads/budget.xlsx",
        ...     content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ...     sheet_schemas=[{
        ...         "sheet_name": "Q4_Budget",
        ...         "sheet_index": 0,
        ...         "schema": {"fields": {...}}
        ...     }]
        ... )]
        >>> xml = convert_excel_schemas_to_xml(files)
    """
    converter = ExcelSchemaToXmlConverter()
    return converter.convert_files(files)


# Helper function for single file conversion
def convert_single_excel_schema_to_xml(file: ExcelFileSchema) -> str:
    """
    Convert a single Excel file schema to XML.

    Args:
        file: ExcelFileSchema object

    Returns:
        XML string for a single <file> element
    """
    converter = ExcelSchemaToXmlConverter()
    return converter.convert_file(file)


if __name__ == "__main__":
    # Example usage
    example_file = ExcelFileSchema(
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
                        "oct": {"type": "int", "range": "C2:C5"},
                        "nov": {"type": "int", "range": "D2:D5"},
                        "dec": {"type": "int", "range": "E2:E5"}
                    }
                }
            }
        ]
    )

    # Using the class
    converter = ExcelSchemaToXmlConverter()
    xml_output = converter.convert_files([example_file])
    print(xml_output)

    # Using the standalone function
    xml_output2 = convert_excel_schemas_to_xml([example_file])
    print("\n" + "="*50 + "\n")
    print(xml_output2)
