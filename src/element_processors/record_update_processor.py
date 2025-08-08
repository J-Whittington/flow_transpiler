"""
Processor for Flow record update elements.
"""
import logging
from typing import Optional, List
import xml.etree.ElementTree as ET

from element_processors.base_processor import BaseElementProcessor
from models import FlowElementMap


class RecordUpdateProcessor(BaseElementProcessor):
    """
    Processor for Flow record update elements.
    
    This processor handles the conversion of Flow record update elements into Apex-like
    pseudocode. It processes field assignments and generates record update statements.
    """
    
    def process(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a record update element and generate pseudocode.
        
        Args:
            element: The record update element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
        """
        # Process field assignments
        assignments = element.findall(f"{namespace}inputAssignments")
        if not assignments:
            self.line_builder.add_comment("ERROR: No field assignments found in record update")
            return
            
        # Process each assignment
        for assignment in assignments:
            field_elem = assignment.find(f"{namespace}field")
            value_elem = assignment.find(f".//{namespace}elementReference")
            
            if not (field_elem is not None and hasattr(field_elem, 'text') and 
                   value_elem is not None and hasattr(value_elem, 'text')):
                self.line_builder.add_comment("ERROR: Invalid field assignment found")
                continue
                
            self.line_builder.add(f"recordToUpdate.{field_elem.text} = {value_elem.text};")
        
        # Add update statement
        self.line_builder.add("update recordToUpdate;") 