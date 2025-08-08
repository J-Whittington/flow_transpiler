"""
Processor for Flow subflow elements.
"""
import xml.etree.ElementTree as ET
from typing import Dict, List

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap


class SubflowProcessor(BaseElementProcessor):
    """
    Processor for Flow subflow elements.
    
    This processor handles the conversion of Flow subflow elements into Apex-like
    method calls. It processes input parameters and generates the appropriate
    method invocation.
    """
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a subflow element and generate pseudocode.
        
        Args:
            element: The subflow element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
            
        Raises:
            ElementProcessingError: If the subflow cannot be processed
        """
        # Get subflow name
        name_elem = element.find(f"{namespace}name")
        if name_elem is None:
            return
            
        subflow_name = name_elem.text
        
        # Process input parameters (handle both inputParameters and inputAssignments)
        params = []
        
        # Check for inputParameters
        input_params = element.findall(f"{namespace}inputParameters")
        for param in input_params:
            name = param.find(f"{namespace}name")
            value = param.find(f"{namespace}value")
            if name is not None and value is not None:
                value_text = self._get_parameter_value(value, namespace)
                params.append(f"{name.text}: {value_text}")
        
        # Check for inputAssignments
        input_assignments = element.findall(f"{namespace}inputAssignments")
        for assignment in input_assignments:
            name = assignment.find(f"{namespace}name")
            value = assignment.find(f"{namespace}value")
            if name is not None and value is not None:
                value_text = self._get_parameter_value(value, namespace)
                params.append(f"{name.text}: {value_text}")
        
        # Add subflow call
        if params:
            self.line_builder.add(f"{subflow_name}({', '.join(params)});")
        else:
            self.line_builder.add(f"{subflow_name}();")
    
    def _get_parameter_value(self, value_elem: ET.Element, namespace: str) -> str:
        """
        Get the parameter value from the value element.
        
        Args:
            value_elem: The value element
            namespace: The XML namespace
            
        Returns:
            The parameter value as a string
        """
        # Check for element reference
        element_ref = value_elem.find(f"{namespace}elementReference")
        if element_ref is not None and hasattr(element_ref, 'text'):
            return element_ref.text
            
        # Check for string value
        string_value = value_elem.find(f"{namespace}stringValue")
        if string_value is not None and hasattr(string_value, 'text'):
            return f'"{string_value.text}"'
            
        # Check for number value
        number_value = value_elem.find(f"{namespace}numberValue")
        if number_value is not None and hasattr(number_value, 'text'):
            return number_value.text
            
        # Check for boolean value
        boolean_value = value_elem.find(f"{namespace}booleanValue")
        if boolean_value is not None and hasattr(boolean_value, 'text'):
            return boolean_value.text.lower()
            
        return "null"
