"""
Processor for Flow loop elements.
"""
import logging
from typing import List, Optional, Tuple
import xml.etree.ElementTree as ET

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap


class LoopProcessor(BaseElementProcessor):
    """
    Processor for Flow loop elements.
    
    This processor handles the conversion of Flow loop elements into Apex-like
    for loops. It processes collection references and generates appropriate
    loop variable declarations.
    """
    
    def __init__(self, line_builder, variable_tracker, element_chain_processor):
        """
        Initialize the loop processor.
        
        Args:
            line_builder: LineBuilder instance for generating output
            variable_tracker: FlowVariableTracker instance for tracking variables
            element_chain_processor: ElementChainProcessor instance for processing element chains
        """
        super().__init__(line_builder, variable_tracker)
        self.element_chain_processor = element_chain_processor
        self.logger = logging.getLogger(__name__)
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a loop element and generate pseudocode.
        
        Args:
            element: The loop element to process
            namespace: XML namespace
            element_map: Map of all flow elements
        """
        name = self._get_element_name(element, namespace)
        self.logger.debug(f"Processing loop element: {name}")
        
        collection_name = self._get_collection_reference(element, namespace, name)
        if not collection_name:
            return
            
        collection_type = self._determine_collection_type(collection_name, element_map, namespace)
        self.logger.debug(f"Collection type: {collection_type}")
        
        loop_var = self._generate_loop_variable_name(collection_name)
        self.logger.debug(f"Generated loop variable: {loop_var}")
        
        self.variable_tracker.add_loop_mapping(name, loop_var)
        self.line_builder.add_comment(f"Loop - {name}")
        
        self._generate_loop_structure(collection_type, loop_var, collection_name)
        self._process_next_value(element, namespace, element_map, loop_var, collection_name)
        self.line_builder.end_block()
        self.line_builder.add("}")
        
        self._process_no_more_values(element, namespace, element_map)
    
    def _get_element_name(self, element: ET.Element, namespace: str) -> str:
        """Get the name of the element."""
        name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
        return name_elem.text if name_elem is not None and hasattr(name_elem, 'text') else "unnamed"
    
    def _get_collection_reference(self, element: ET.Element, namespace: str, name: str) -> Optional[str]:
        """Get the collection reference from the element."""
        collection_ref = element.find(f"{namespace}collectionReference")
        if collection_ref is None or not hasattr(collection_ref, 'text'):
            self.logger.error(f"No collection reference found for loop {name}")
            self.line_builder.add_comment(f"ERROR: No collection reference found for loop {name}")
            return None
        collection_name = collection_ref.text
        self.logger.debug(f"Collection reference: {collection_name}")
        return collection_name
    
    def _generate_loop_structure(self, collection_type: str, loop_var: str, collection_name: str) -> None:
        """Generate the loop structure with proper indentation."""
        self.line_builder.add(f"for ({collection_type} {loop_var} : {collection_name}) {{")
        self.line_builder.begin_block()
        self.line_builder.add_comment("Start of loop block")
    
    def _process_next_value(self, element: ET.Element, namespace: str, element_map: FlowElementMap, loop_var: str, collection_name: str) -> None:
        """
        Process the next value in the loop.
        
        Args:
            element: The loop element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
            loop_var: The name of the loop variable
            collection_name: The name of the collection being looped over
        """
        self.logger.debug(f"Processing next value with loop variable: {loop_var}")
        
        next_value = element.find(f"{namespace}nextValueConnector")
        if next_value is None:
            self.logger.warning("No next value connector found in loop element")
            self.line_builder.add_comment("Process SObject record")
            return
            
        target_ref = next_value.find(f"{namespace}targetReference")
        if target_ref is None or not hasattr(target_ref, 'text'):
            self.logger.warning("No target reference found in next value connector")
            self.line_builder.add_comment("Process SObject record")
            return
            
        target_name = target_ref.text
        self.logger.debug(f"Found target reference: {target_name}")
        
        target_element = self._find_target_element(target_name, element_map)
        if target_element is None:
            self.logger.warning(f"Target element {target_name} not found")
            self.line_builder.add_comment("Process SObject record")
            return
            
        try:
            loop_id = element.get('id', id(element))
            self.element_chain_processor.push_loop_context(loop_id, loop_var, collection_name)
            self.element_chain_processor.process_chain(target_element, namespace, element_map)
        finally:
            self.element_chain_processor.pop_loop_context()
    
    def _process_no_more_values(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """Process the no more values connector."""
        no_more = element.find(f"{namespace}noMoreValuesConnector")
        if no_more is None:
            self.logger.warning("No no more values connector found in loop element")
            self.line_builder.add_comment("Process SObject record")
            return
            
        target_ref = no_more.find(f"{namespace}targetReference")
        if target_ref is None or not hasattr(target_ref, 'text'):
            self.logger.warning("No target reference found in no more values connector")
            self.line_builder.add_comment("Process SObject record")
            return
            
        target_name = target_ref.text
        self.logger.debug(f"Found no more values target reference: {target_name}")
        
        target_element = self._find_target_element(target_name, element_map)
        if target_element is None:
            self.logger.warning(f"Target element {target_name} not found")
            self.line_builder.add_comment("Process SObject record")
            return
            
        self.element_chain_processor.process_chain(target_element, namespace, element_map)
    
    def _find_target_element(self, target_name: str, element_map: FlowElementMap) -> Optional[ET.Element]:
        """Find a target element in the element map."""
        for element_type, elements in element_map.items():
            if isinstance(elements, dict) and target_name in elements:
                self.logger.debug(f"Found target element of type: {element_type}")
                return elements[target_name]
        return None
    
    def _generate_loop_variable_name(self, collection_name: str) -> str:
        """
        Generate a loop variable name from a collection name.
        
        Args:
            collection_name: The name of the collection
            
        Returns:
            A suitable loop variable name
        """
        base_name = collection_name.replace("_", "")
        loop_var = base_name[0].lower()
        self.logger.debug(f"Generated loop variable '{loop_var}' from collection '{collection_name}'")
        return loop_var
    
    def _determine_collection_type(self, collection_name: str, element_map: FlowElementMap, namespace: str) -> str:
        """
        Determine the type of a collection by looking at its source.
        
        Args:
            collection_name: Name of the collection variable
            element_map: Map of all flow elements
            namespace: XML namespace
        Returns:
            Type name for the collection elements
        """
        self.logger.debug(f"Determining collection type for: {collection_name}")
        
        collection_type = self.variable_tracker.get_type(collection_name)
        if collection_type:
            self.logger.debug(f"Found type in variable tracker: {collection_type}")
            if collection_type.startswith('List<'):
                inner_type = collection_type[5:-1]
                self.logger.debug(f"Extracted inner type: {inner_type}")
                return inner_type
            return collection_type
            
        for element_type, elements in element_map.items():
            if element_type == 'recordLookups' and isinstance(elements, dict):
                for name, elem in elements.items():
                    if name == collection_name:
                        object_type = elem.find(f"{namespace}object")
                        if object_type is not None and hasattr(object_type, 'text'):
                            type_name = object_type.text
                            self.logger.debug(f"Found type from record lookup: {type_name}")
                            self.variable_tracker.add_variable(collection_name, f"List<{type_name}>")
                            return type_name
                            
        self.logger.debug("No type found, defaulting to SObject")
        return 'SObject'
