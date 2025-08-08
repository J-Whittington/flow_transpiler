"""
Processor for Flow action call elements.
"""
import xml.etree.ElementTree as ET
from typing import List

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap


class ActionProcessor(BaseElementProcessor):
    """
    Processor for Flow action call elements.
    
    This processor handles the conversion of Flow action call elements into Apex-like
    method calls. It processes input parameters and generates the appropriate
    method invocation.
    """
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process an action call element and generate pseudocode.
        
        Args:
            element: The action call element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
            
        Raises:
            ElementProcessingError: If the action call cannot be processed
        """

        # Get action name
        name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
        if name_elem is None or not hasattr(name_elem, 'text'):
            raise ElementProcessingError("action", "Missing required name element")
            
        action_name = name_elem.text
        self.add_section_header("Action", action_name)
        
        # Process input parameters
        params = self._process_input_parameters(element, namespace)
        
        # Generate the method call
        if params:
            param_str = ", ".join(params)
            self.add_line(f"{action_name}({param_str});")
        else:
            self.add_line(f"{action_name}();")
    
    def _process_input_parameters(self, element: ET.Element, namespace: str) -> List[str]:
        """
        Process input parameters for the action call.
        
        Args:
            element: The action call element to process
            namespace: XML namespace for element queries
            
        Returns:
            List of formatted parameter strings
        """
        params = []
        
        for param in element.findall(f"{namespace}inputParameters"):
            value_ref = param.find(f".//{namespace}elementReference")
            if value_ref is None or not hasattr(value_ref, 'text'):
                continue
                
            value = value_ref.text
            
            # Handle special cases for value references
            if value.startswith('$Record.'):
                value = f"record.{value[8:]}"
            elif value.startswith('$Loop.'):
                # TODO: [FLOW-125] Enhance loop variable handling
                # We need to:
                # 1. Track current loop context
                # 2. Handle nested loops
                # 3. Generate proper loop variable references
                self.add_comment(f"Loop variable reference: {value}")
                continue
                
            params.append(value)
            
        return params
