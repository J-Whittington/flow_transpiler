"""
Processor for Flow record create elements.
"""
import logging
from typing import Optional, List
import xml.etree.ElementTree as ET

from element_processors.base_processor import BaseElementProcessor
from models import FlowElementMap


class RecordCreateProcessor(BaseElementProcessor):
    """
    Processor for Flow record create elements.
    
    This processor handles the conversion of Flow record create elements into Apex-like
    pseudocode. It processes field assignments and generates record create statements.
    """
    
    def process(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a record create element and generate pseudocode.
        
        Args:
            element: The record create element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
        """
        # Get the object type
        object_elem = element.find(f"{namespace}object")
        object_type = object_elem.text if object_elem is not None and hasattr(object_elem, 'text') else "SObject"
        
        # Get variable name if specified
        output_ref = element.find(f"{namespace}outputReference")
        var_name = output_ref.text if output_ref is not None and hasattr(output_ref, 'text') else "newRecord"
        
        # Process field assignments
        assignments = element.findall(f"{namespace}inputAssignments")
        if not assignments:
            self.line_builder.add(f"{object_type} {var_name} = new {object_type}();")
            self.line_builder.add(f"insert {var_name};")
            return
        
        # Generate Apex-style constructor
        self.line_builder.add(f"{object_type} {var_name} = new {object_type}(")
        self.line_builder.begin_block()
        
        # Process each assignment as constructor parameter
        valid_assignments = []
        for assignment in assignments:
            field_elem = assignment.find(f"{namespace}field")
            value_elem = assignment.find(f".//{namespace}elementReference")
            
            if field_elem is not None and hasattr(field_elem, 'text'):
                if value_elem is not None and hasattr(value_elem, 'text'):
                    valid_assignments.append((field_elem.text, value_elem.text))
                else:
                    # Check for other value types
                    value = self._get_assignment_value(assignment, namespace)
                    if value != "unknown":
                        valid_assignments.append((field_elem.text, value))
                    else:
                        self.line_builder.add("// ERROR: Invalid field assignment found")
        
        # Add field assignments as constructor parameters
        for i, (field, value) in enumerate(valid_assignments):
            comma = "," if i < len(valid_assignments) - 1 else ""
            self.line_builder.add(f"{field} = {value}{comma}")
        
        self.line_builder.end_block()
        self.line_builder.add(");")
        self.line_builder.add(f"insert {var_name};")
    
    def _get_assignment_value(self, assignment: ET.Element, namespace: str) -> str:
        """
        Get the assignment value from various possible sources.
        
        Args:
            assignment: The input assignment element
            namespace: XML namespace
            
        Returns:
            The assignment value as a string
        """
        # Check for element reference
        value_elem = assignment.find(f".//{namespace}elementReference")
        if value_elem is not None and hasattr(value_elem, 'text'):
            return value_elem.text
            
        # Check for string value
        string_value = assignment.find(f".//{namespace}stringValue")
        if string_value is not None and hasattr(string_value, 'text'):
            return f"'{string_value.text}'"
            
        # Check for boolean value
        boolean_value = assignment.find(f".//{namespace}booleanValue")
        if boolean_value is not None and hasattr(boolean_value, 'text'):
            return boolean_value.text.lower()
            
        # Check for number value
        number_value = assignment.find(f".//{namespace}numberValue")
        if number_value is not None and hasattr(number_value, 'text'):
            return number_value.text
            
        return "unknown" 