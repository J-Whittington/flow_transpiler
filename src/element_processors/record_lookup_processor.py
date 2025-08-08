"""
Processor for Flow record lookup elements.
"""
import logging
from typing import List, Optional
import xml.etree.ElementTree as ET
import ast

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap
from utils.operator_formatter import FlowOperatorFormatter


class RecordLookupProcessor(BaseElementProcessor):
    """
    Processor for Flow record lookup elements.
    
    This processor handles the conversion of Flow record lookup elements into Apex-like
    SOQL queries. It processes filters, output references, and generates appropriate
    variable declarations.
    """
    
    def __init__(self, line_builder, variable_tracker):
        """
        Initialize the record lookup processor.
        
        Args:
            line_builder: LineBuilder instance for generating output
            variable_tracker: FlowVariableTracker instance for tracking variables
        """
        super().__init__(line_builder, variable_tracker)
        self.operator_formatter = FlowOperatorFormatter()
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a record lookup element and generate pseudocode.
        
        Args:
            element: The record lookup element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
            
        Raises:
            ElementProcessingError: If the lookup cannot be processed
        """
        # Get lookup name
        name_elem = element.find(f"{namespace}n")
        if name_elem is None:
            name_elem = element.find(f"{namespace}name")
        if name_elem is None:
            name_elem = element.find("name")
        if name_elem is None or not hasattr(name_elem, 'text'):
            raise ElementProcessingError("record lookup", "Missing required name element")
        lookup_name = name_elem.text
        
        # Get object type
        object_type = element.find(f"{namespace}object")
        if object_type is None:
            object_type = element.find("object")
        if object_type is None or not hasattr(object_type, 'text'):
            raise ElementProcessingError("record lookup", "Missing required object type")
        object_name = object_type.text
        
        # Get output reference
        output_ref = element.find(f"{namespace}outputReference")
        if output_ref is None:
            output_ref = element.find("outputReference")
        if output_ref is not None and hasattr(output_ref, 'text') and output_ref.text:
            output_name = output_ref.text
        elif 'outputReference' in element.attrib:
            output_name = element.attrib['outputReference']
        else:
            output_name = lookup_name
        
        # Get queried fields
        queried_fields = []
        for field in element.findall(f"{namespace}queriedFields"):
            if field is not None and hasattr(field, 'text'):
                queried_fields.append(field.text)
        
        # If no fields specified, default to Id
        if not queried_fields:
            queried_fields = ["Id"]
        
        # Check if we should get only first record
        get_first = element.find(f"{namespace}getFirstRecordOnly")
        if get_first is None:
            get_first = element.find("getFirstRecordOnly")
        get_first_only = get_first is not None and hasattr(get_first, 'text') and get_first.text.lower() == 'true'
        
        # Track the variable and its type
        if get_first_only:
            self.variable_tracker.add_variable(output_name, object_name)
        else:
            self.variable_tracker.add_variable(output_name, f"List<{object_name}>")
        
        # Process filters
        filters = self._process_filters(element, namespace)
        
        # Build query
        query_lines = self._build_soql_query(object_name, queried_fields, filters, get_first_only)
        
        # Add the query to the output using the output reference name
        if get_first_only:
            self.line_builder.add(f"{object_name} {output_name} = [")
        else:
            self.line_builder.add(f"List<{object_name}> {output_name} = [")
        self.line_builder.begin_block()
        for line in query_lines:
            self.line_builder.add(line)
        self.line_builder.end_block()
        self.line_builder.add("];")
    
    def _process_filters(self, element: ET.Element, namespace: str) -> List[str]:
        """
        Process filters from the record lookup element.
        
        Args:
            element: The record lookup element to process
            namespace: XML namespace for element queries
            
        Returns:
            List of filter conditions
        """
        filters = []
        for filter_elem in element.findall(f"{namespace}filters"):
            field = filter_elem.find(f"{namespace}field")
            if field is None or not hasattr(field, 'text'):
                continue
                
            field_name = field.text
            operator = filter_elem.find(f"{namespace}operator")
            operator_text = operator.text if operator is not None and hasattr(operator, 'text') else "="
            
            value = filter_elem.find(f"{namespace}value")
            if value is None:
                continue
                
            condition = self._build_filter_condition(field_name, operator_text, value, namespace)
            if condition:
                filters.append(condition)
        
        return filters
    
    def _build_filter_condition(self, field_name: str, operator_text: str, value: ET.Element, namespace: str) -> Optional[str]:
        """
        Build a single filter condition from field, operator, and value.
        
        Args:
            field_name: Name of the field to filter on
            operator_text: Operator to use in the condition
            value: Value element containing the filter value
            namespace: XML namespace for element queries
            
        Returns:
            Formatted filter condition or None if invalid
        """
        # Handle element references
        element_ref = value.find(f"{namespace}elementReference")
        if element_ref is not None and hasattr(element_ref, 'text'):
            return self._build_reference_condition(field_name, operator_text, element_ref.text)
            
        # Handle literal values
        value_text = self._extract_literal_value(value, namespace)
        if value_text is None:
            return None
            
        return self._build_literal_condition(field_name, operator_text, value_text)
    
    def _build_reference_condition(self, field_name: str, operator_text: str, reference: str) -> str:
        """Build a condition using a field reference."""
        value_text = reference.replace('$Record.', 'record.')
        formatted_operator = self._format_soql_operator(operator_text)
        return f"{field_name} {formatted_operator} {value_text}"
    
    def _extract_literal_value(self, value: ET.Element, namespace: str) -> Optional[str]:
        """Extract literal value from value element."""
        string_value = value.find(f"{namespace}stringValue")
        boolean_value = value.find(f"{namespace}booleanValue")
        
        if string_value is not None and hasattr(string_value, 'text'):
            return string_value.text
        if boolean_value is not None and hasattr(boolean_value, 'text'):
            return boolean_value.text
        if hasattr(value, 'text'):
            return value.text
        return None
    
    def _build_literal_condition(self, field_name: str, operator_text: str, value_text: str) -> str:
        """Build a condition using a literal value."""
        if operator_text == 'Contains':
            return f"{field_name} LIKE '%{value_text}%'"
            
        formatted_operator = self._format_soql_operator(operator_text)
        if str(value_text).lower() in ("true", "false"):
            return f"{field_name} {formatted_operator} {str(value_text).lower()}"
        return f"{field_name} {formatted_operator} '{value_text}'"
    
    def _format_soql_operator(self, operator: str) -> str:
        """Format operator for SOQL syntax."""
        formatted = self.operator_formatter.format_operator(operator)
        return "=" if formatted == "==" else formatted
    
    def _build_soql_query(self, object_name: str, queried_fields: List[str], filters: List[str], get_first_only: bool) -> List[str]:
        """
        Build SOQL query lines.
        
        Args:
            object_name: Name of the object to query
            queried_fields: List of fields to query
            filters: List of filter conditions
            get_first_only: Whether to limit to first record
            
        Returns:
            List of query lines
        """
        query_lines = [
            f"SELECT {', '.join(queried_fields)}",
            f"FROM {object_name}"
        ]
        if filters:
            query_lines.append(f"WHERE {' AND '.join(filters)}")
        if get_first_only:
            query_lines.append("LIMIT 1")
        return query_lines
