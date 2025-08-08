"""
Processor for Flow record elements.
"""
import logging
from typing import List, Optional
import xml.etree.ElementTree as ET

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap


class AssignmentProcessor(BaseElementProcessor):
    """
    Processor for Flow record elements.
    
    This processor handles the conversion of Flow record elements into Apex-like
    pseudocode. It processes record updates, creates, and deletes.
    """
    
    def __init__(self, line_builder, variable_tracker, formula_processor=None, element_chain_processor=None):
        """
        Initialize the record processor.
        
        Args:
            line_builder: LineBuilder instance for generating output
            variable_tracker: FlowVariableTracker instance for tracking variables
            formula_processor: Optional FormulaProcessor instance for handling formula references
            element_chain_processor: Optional ElementChainProcessor instance for handling element chains
        """
        super().__init__(line_builder, variable_tracker)
        self.formula_processor = formula_processor
        self.element_chain_processor = element_chain_processor
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process an assignment element and generate pseudocode for variable assignments.
        
        Args:
            element: The assignment element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
        """
        assignment_name = self._get_assignment_name(element, namespace)
        self._process_assignment_items(element, namespace)
        self._process_connector(element, namespace, element_map)
    
    def _get_assignment_name(self, element: ET.Element, namespace: str) -> str:
        """Get the assignment name from the element."""
        name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
        if name_elem is None or not hasattr(name_elem, 'text'):
            raise ElementProcessingError("assignment", "Missing required name element")
        return name_elem.text
    
    def _process_assignment_items(self, element: ET.Element, namespace: str) -> None:
        """Process all assignment items in the element."""
        for item in element.findall(f"{namespace}assignmentItems"):
            target = self._get_target_reference(item, namespace, element)
            value = self._get_value_reference(item, namespace, element)
            
            if self._is_list_addition_in_loop(target):
                self._handle_list_addition(target)
            else:
                self.line_builder.add(f"{target} = {value};")
    
    def _is_list_addition_in_loop(self, target: str) -> bool:
        """Check if this is a list addition within a loop context."""
        if not (self.element_chain_processor and self.element_chain_processor.is_in_loop()):
            return False
            
        # Check if target looks like a collection (ends with List, Set, etc.)
        collection_suffixes = ['List', 'Set', 'Collection']
        return any(target.endswith(suffix) for suffix in collection_suffixes)
    
    def _handle_list_addition(self, target: str) -> None:
        """Handle list addition operations in loop context."""
        loop_var = self.element_chain_processor.get_current_loop_var()
        self.line_builder.add(f"{target}.add({loop_var});")
        
    
    def _process_connector(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """Process connector element if present."""
        connector = element.find(f"{namespace}connector")
        if connector is None:
            return
            
        target_ref = connector.find(f"{namespace}targetReference")
        if target_ref is None or not hasattr(target_ref, 'text'):
            return
            
        target_element = self._find_target_element(target_ref.text, element_map)
        if target_element is not None:
            self._create_and_process_method(target_ref.text, target_element, namespace, element_map)
    
    def _find_target_element(self, target_ref: str, element_map: FlowElementMap):
        """Find the target element in the element map."""
        for element_type, elements in element_map.items():
            if isinstance(elements, dict) and target_ref in elements:
                return elements[target_ref]
        return None
    
    def _create_and_process_method(self, target_name: str, target_element: ET.Element, 
                                 namespace: str, element_map: FlowElementMap) -> None:
        """Create a new method and process the target element."""
        self.line_builder.new_method(target_name)
        
        if self.element_chain_processor:
            self.element_chain_processor.process_chain(target_element, namespace, element_map)
        
        self.line_builder.end_method()
        self.line_builder.add(f"{target_name}();")
    
    def _get_target_reference(self, item: ET.Element, namespace: str, element: ET.Element) -> str:
        """
        Get the target reference for an assignment.
        
        Args:
            item: The assignment item element
            namespace: XML namespace for element queries
            element: The parent assignment element
            
        Returns:
            The target reference in Apex syntax
        """
        assign_to = item.find(f"{namespace}assignToReference")
        if assign_to is None or not hasattr(assign_to, 'text'):
            return "unknown"
            
        target = assign_to.text
        return self._process_reference(target, namespace, element)
    
    def _get_value_reference(self, item: ET.Element, namespace: str, element: ET.Element) -> str:
        """
        Get the value reference for an assignment.
        
        Args:
            item: The assignment item element
            namespace: XML namespace for element queries
            element: The parent assignment element
            
        Returns:
            The value reference in Apex syntax
        """
        # Check for element reference
        value_ref = item.find(f".//{namespace}elementReference")
        if value_ref is not None and hasattr(value_ref, 'text'):
            value = value_ref.text
            return self._process_reference(value, namespace, element)
        
        # Check for string value
        string_value = item.find(f".//{namespace}stringValue")
        if string_value is not None and hasattr(string_value, 'text'):
            return f"'{string_value.text}'"
        
        # Check for boolean value
        boolean_value = item.find(f".//{namespace}booleanValue")
        if boolean_value is not None and hasattr(boolean_value, 'text'):
            return boolean_value.text.lower()
        
        return "unknown"
    
    def _process_reference(self, reference: str, namespace: str, element: ET.Element) -> str:
        """
        Process a reference and convert it to Apex syntax.
        
        Args:
            reference: The reference to process
            namespace: XML namespace for element queries
            element: The parent assignment element
            
        Returns:
            The processed reference in Apex syntax
        """
        # Handle formula references
        if self.formula_processor and reference in self.formula_processor.formula_functions:
            return f"{self.formula_processor.get_formula_function(reference)}()"
        
        # Handle record references
        if reference.startswith('$Record.'):
            return f"record.{reference[8:]}"
        
        # Handle loop references
        if reference.startswith('$Loop.'):
            loop_var = self._get_loop_variable(element, namespace)
            return f"{loop_var}.{reference[6:]}"
        
        # Handle other Flow variables
        if reference.startswith('$'):
            return reference[1:]
        
        # If we're in a loop and the reference starts with the collection name, use the loop variable
        if self.element_chain_processor and self.element_chain_processor.is_in_loop():
            loop_var = self.element_chain_processor.get_current_loop_var()
            collection = self.element_chain_processor.get_current_collection()
            if loop_var and collection and reference.startswith(collection):
                # Split on the first dot to handle nested references
                parts = reference.split('.', 1)
                if len(parts) > 1:
                    return f"{loop_var}.{parts[1]}"
                return loop_var
            
            # Special handling for list additions in loop context
            if reference == 'LeadList':
                return reference
            
            # Check if this is a reference to a collection we know about
            loop_var = self.variable_tracker.get_loop_variable(reference)
            if loop_var:
                return loop_var
        
        # Check if we're in a loop context
        if self.element_chain_processor and self.element_chain_processor.is_in_loop():
            loop_var = self.element_chain_processor.get_current_loop_var()
            if loop_var:
                # Check if this is a reference to the loop variable
                loop_name = self.variable_tracker.get_loop_name_for_var(loop_var)
                if loop_name and reference.startswith(loop_name):
                    # Split on first dot to handle nested references
                    parts = reference.split('.', 1)
                    if len(parts) > 1:
                        return f"{loop_var}.{parts[1]}"
                    return loop_var
        
        return reference
    
    def _get_loop_variable(self, element: ET.Element, namespace: str) -> str:
        """
        Get the current loop variable name.
        
        Args:
            element: The parent assignment element
            namespace: XML namespace for element queries
            
        Returns:
            The current loop variable name
        """
        # First try to get it from the element chain processor
        if self.element_chain_processor:
            loop_var = self.element_chain_processor.get_current_loop_var()
            if loop_var:
                return loop_var
        
        # If not in a loop, try to extract from collection reference
        collection_ref = element.find(f"{namespace}collectionReference")
        if collection_ref is not None and hasattr(collection_ref, 'text'):
            collection = collection_ref.text
            # Always use the first letter of the collection name
            loop_var = collection.lower().replace("_", "")[0]
            return loop_var
        
        return "unknown"
    
    def _get_collection_name(self, element: ET.Element, namespace: str) -> Optional[str]:
        """
        Get the collection name from the element.
        
        Args:
            element: The parent assignment element
            namespace: XML namespace for element queries
            
        Returns:
            The collection name if found, None otherwise
        """
        collection_ref = element.find(f"{namespace}collectionReference")
        if collection_ref is not None and hasattr(collection_ref, 'text'):
            return collection_ref.text
        return None
