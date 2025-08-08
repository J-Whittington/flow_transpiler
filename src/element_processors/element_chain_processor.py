"""
Processor for handling element chains in Flow XML.

This module provides the ElementChainProcessor class which is responsible for traversing
and processing connected elements in a Salesforce Flow XML structure. It handles:
- Processing elements in sequence based on their connectors
- Cycle detection to prevent infinite loops
- Special handling of decision and loop elements
- Tracking of loop variables for context
- Proper element map resolution for connected elements

The processor maintains state about the current processing path and processed elements
to ensure each element is processed exactly once (unless it's a decision or loop path).
"""
import logging
from typing import Optional, Dict, Set, List, NamedTuple
import xml.etree.ElementTree as ET

from element_processors.base_processor import BaseElementProcessor
from models import FlowElementMap
from utils.line_builder import LineBuilder
from utils.variable_tracker import FlowVariableTracker


class LoopContext(NamedTuple):
    """Represents the context of a loop being processed."""
    loop_id: str
    loop_var: str
    collection: str


class ElementChainProcessor:
    """
    Handles processing of element chains in Flow XML.
    
    This class is responsible for traversing and processing connected elements
    in a Flow, handling cycle detection, and managing the processing order.
    
    The processor works by:
    1. Starting with an initial element
    2. Processing it using the appropriate processor for its type
    3. Following any connectors to subsequent elements
    4. Handling special cases like decisions and loops
    5. Maintaining state to prevent cycles and track context
    6. Creating methods for elements that are referenced multiple times
    
    The element map structure should be:
    {
        'elementType': {
            'elementName': element
        }
    }
    """
    
    def __init__(self, processors: Dict[str, BaseElementProcessor], line_builder: LineBuilder, variable_tracker: FlowVariableTracker):
        """
        Initialize the ElementChainProcessor.
        
        Args:
            processors: Dictionary mapping element types to their processors
            line_builder: Builder for generating code lines
            variable_tracker: Tracker for flow variables
        """
        self.processors = processors
        self.line_builder = line_builder
        self.variable_tracker = variable_tracker
        self.processed_elements: Set[str] = set()
        self.current_path: List[str] = []
        self.loop_stack: List[LoopContext] = []
        self.goto_targets: Set[str] = set()  # Elements that are targets of isGoTo connectors
        self.goto_methods: Set[str] = set()  # Methods that have been created for goto targets
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initialized ElementChainProcessor")
    
    def reset(self) -> None:
        """Reset all tracking state."""
        self.processed_elements.clear()
        self.current_path.clear()
        self.loop_stack.clear()
        self.goto_targets.clear()
        self.goto_methods.clear()
        self.logger.debug("Reset processor state")
    
    def is_in_loop(self) -> bool:
        """
        Check if we're currently in a loop context.
        
        Returns:
            True if we're in a loop context, False otherwise
        """
        in_loop = len(self.loop_stack) > 0
        self.logger.debug(f"Checking loop context: {in_loop} (loop stack depth: {len(self.loop_stack)})")
        return in_loop
    
    def get_current_loop_var(self) -> Optional[str]:
        """
        Get the current loop variable name.
        
        Returns:
            The current loop variable name if in a loop, None otherwise
        """
        if not self.loop_stack:
            return None
        loop_var = self.loop_stack[-1].loop_var
        self.logger.debug(f"Getting current loop variable: {loop_var}")
        return loop_var
    
    def get_current_collection(self) -> Optional[str]:
        """
        Get the current collection name if in a loop context.
        """
        if not self.loop_stack:
            return None
        return self.loop_stack[-1].collection
    
    def push_loop_context(self, loop_id: str, loop_var: str, collection: str) -> None:
        """
        Push a new loop context onto the stack.
        
        Args:
            loop_id: The ID of the loop element
            loop_var: The loop variable name
            collection: The collection being iterated over
        """
        context = LoopContext(loop_id, loop_var, collection)
        self.loop_stack.append(context)
        self.logger.debug(f"Pushed loop context: {context}")
    
    def pop_loop_context(self) -> None:
        """Pop the current loop context from the stack."""
        if self.loop_stack:
            context = self.loop_stack.pop()
            self.logger.debug(f"Popped loop context: {context}")
    
    def scan_for_goto_targets(self, element_map: FlowElementMap, namespace: str) -> None:
        """
        Scan the flow to identify elements that are targets of isGoTo connectors.
        Only considers regular connectors and defaultConnectors, not faultConnectors
        which are used for error handling.
        
        Args:
            element_map: Map of element names to elements
            namespace: XML namespace for element queries
        """
        self.logger.debug("Scanning for isGoTo targets")
        for element_type, elements in element_map.items():
            if isinstance(elements, dict):
                for element_name, element in elements.items():
                    # Only check regular connectors and defaultConnectors for isGoTo
                    # faultConnectors are for error handling and shouldn't create separate methods
                    connector_types = ['connector', 'defaultConnector']
                    for connector_type in connector_types:
                        for connector in element.findall(f".//{namespace}{connector_type}"):
                            is_goto = connector.find(f"{namespace}isGoTo")
                            if is_goto is not None and is_goto.text == "true":
                                target_ref = connector.find(f"{namespace}targetReference")
                                if target_ref is not None and hasattr(target_ref, 'text'):
                                    self.goto_targets.add(target_ref.text)
                                    self.logger.debug(f"Found isGoTo target: {target_ref.text}")
        
        self.logger.debug(f"Total isGoTo targets found: {list(self.goto_targets)}")

    def _should_create_method(self, element_name: str) -> bool:
        """
        Check if a method should be created for an element.
        
        Args:
            element_name: Name of the element to check
            
        Returns:
            True if a method should be created, False otherwise
        """
        # Create method if element is a goto target and we haven't created it yet
        return element_name in self.goto_targets and element_name not in self.goto_methods
    
    def process_chain(self, 
                     element: ET.Element, 
                     namespace: str, 
                     element_map: FlowElementMap, 
                     parent_element: Optional[ET.Element] = None) -> None:
        """
        Process a chain of elements starting from the given element.
        Delegates element info, cycle detection, element processing, and connector handling to helpers.
        """
        if not isinstance(element, ET.Element):
            self.logger.error(f"Invalid element type: {type(element)}")
            return

        element_name, element_id = self._get_element_info(element, namespace)
        parent_name = self._get_parent_name(parent_element, namespace)
        self.logger.debug(f"Processing chain element: {element_name} (from parent: {parent_name})")

        if not self._check_for_cycles(element_id, element_name):
            return

        self.processed_elements.add(element_id)
        self.current_path.append(element_name)
        self.logger.debug(f"Added to processing path: {element_name}")

        try:
            self._process_element(element, namespace, element_map, element_name, element_id)
            self._process_connector(element, namespace, element_map)
        finally:
            if self.current_path:
                removed = self.current_path.pop()
                self.logger.debug(f"Removed from processing path: {removed}")

    def _get_element_info(self, element: ET.Element, namespace: str) -> tuple[str, str]:
        """
        Extract element name and ID for logging and identification.
        """
        name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
        element_name = name_elem.text if name_elem is not None and hasattr(name_elem, 'text') else 'unnamed'
        element_id = element.get('id', id(element))
        return element_name, element_id

    def _get_parent_name(self, parent_element: Optional[ET.Element], namespace: str) -> str:
        """
        Extract parent element name for logging.
        """
        if parent_element is not None and isinstance(parent_element, ET.Element):
            parent_name_elem = parent_element.find(f"{namespace}n") or parent_element.find(f"{namespace}name")
            return parent_name_elem.text if parent_name_elem is not None and hasattr(parent_name_elem, 'text') else 'unnamed'
        return "None"

    def _check_for_cycles(self, element_id: str, element_name: str) -> bool:
        """
        Check for cycles in the processing path, considering loop nesting.
        Returns False if a cycle is detected, True otherwise.
        """
        if self.is_in_loop() and element_id == self.loop_stack[-1].loop_id:
            self.logger.debug(f"Returning to loop processor for element {element_name}")
            return False
        if element_id in self.processed_elements:
            if self.is_in_loop():
                if element_id != self.loop_stack[-1].loop_id:
                    self.logger.warning(f"Cycle detected in nested loop at element {element_name}")
                    return False
            else:
                self.logger.warning(f"Cycle detected in flow at element {element_name}")
                return False
        return True

    def _process_element(self, element: ET.Element, namespace: str, element_map: FlowElementMap, element_name: str, element_id: str) -> None:
        """
        Process the element using the appropriate processor.
        Handles method creation for elements used multiple times.
        """
        element_type = element.tag.replace(namespace, '')
        processor = self.processors.get(element_type)
        if processor:
            self.logger.debug(f"Found processor for element type: {element_type}")
            if self._should_create_method(element_name):
                # Mark this goto method as created
                self.goto_methods.add(element_name)
                
                # Analyze what this function should return
                function_returns = self._analyze_function_returns(element, namespace, element_map)
                
                # Generate method signature with returns
                if function_returns:
                    if len(function_returns) == 1:
                        return_type = self.variable_tracker.get_type(function_returns[0])
                        if return_type:
                            self.line_builder.new_method(element_name, return_type)
                        else:
                            self.line_builder.new_method(element_name)
                    else:
                        # Multiple returns - use a comment for now
                        self.line_builder.new_method(element_name)
                        self.line_builder.add(f"// Returns: {', '.join(function_returns)}")
                else:
                    self.line_builder.new_method(element_name)
                
                try:
                    if element_type == 'loop':
                        collection_elem = element.find(f"{namespace}collectionReference")
                        collection = collection_elem.text if collection_elem is not None and hasattr(collection_elem, 'text') else None
                        loop_var = collection[0].lower() if collection else 'item'
                        self.push_loop_context(element_id, loop_var, collection)
                        try:
                            processor.process(element, namespace, element_map)
                        finally:
                            self.pop_loop_context()
                    else:
                        processor.process(element, namespace, element_map)
                    
                    # Add return statement if function has returns
                    if function_returns:
                        if len(function_returns) == 1:
                            self.line_builder.add(f"return {function_returns[0]};")
                        else:
                            # Multiple returns - for now just comment
                            self.line_builder.add(f"// TODO: Return {', '.join(function_returns)}")
                            
                finally:
                    self.line_builder.end_method()
            else:
                if element_type == 'loop':
                    collection_elem = element.find(f"{namespace}collectionReference")
                    collection = collection_elem.text if collection_elem is not None and hasattr(collection_elem, 'text') else None
                    loop_var = collection[0].lower() if collection else 'item'
                    self.push_loop_context(element_id, loop_var, collection)
                    try:
                        processor.process(element, namespace, element_map)
                    finally:
                        self.pop_loop_context()
                else:
                    processor.process(element, namespace, element_map)
        else:
            self.logger.warning(f"No processor found for element type: {element_type}")

    def _process_connector(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process the connector to the next element in the chain.
        """
        # First check if this element has a fault connector - if so, wrap in try-catch
        fault_connector = element.find(f"{namespace}faultConnector")
        has_fault = fault_connector is not None
        
        if has_fault:
            self.line_builder.add("try {")
            self.line_builder.begin_block()
        
        # Process regular connectors
        connector_types = ['connector', 'defaultConnector']
        for connector_type in connector_types:
            connector = element.find(f"{namespace}{connector_type}")
            if connector is not None:
                target_ref = connector.find(f"{namespace}targetReference")
                if target_ref is not None and hasattr(target_ref, 'text'):
                    target_name = target_ref.text
                    self.logger.debug(f"Found target reference: {target_name}")
                    
                    # Check if this is a goto connector
                    is_goto = connector.find(f"{namespace}isGoTo")
                    if is_goto is not None and is_goto.text == "true":
                        # This is a goto call - just add the method call
                        self.line_builder.add(f"{target_name}();")
                        self.logger.debug(f"Added goto method call: {target_name}()")
                    else:
                        # Regular connector - process the chain
                        target_element = None
                        for element_type, elements in element_map.items():
                            if isinstance(elements, dict) and target_name in elements:
                                target_element = elements[target_name]
                                self.logger.debug(f"Found target element of type: {element_type}")
                                break
                        if target_element is not None:
                            # If this target is a goto target that hasn't been processed yet, just call it
                            if target_name in self.goto_targets and target_name in self.goto_methods:
                                self.line_builder.add(f"{target_name}();")
                            else:
                                self.process_chain(target_element, namespace, element_map, element)
                        else:
                            self.logger.error(f"Target element {target_name} not found in element map")
        
        # Handle fault connector in catch block
        if has_fault:
            self.line_builder.end_block()
            self.line_builder.add("} catch (Exception e) {")
            self.line_builder.begin_block()
            
            target_ref = fault_connector.find(f"{namespace}targetReference")
            if target_ref is not None and hasattr(target_ref, 'text'):
                target_name = target_ref.text
                
                # Check if fault connector has isGoTo
                is_goto = fault_connector.find(f"{namespace}isGoTo")
                if is_goto is not None and is_goto.text == "true":
                    self.line_builder.add(f"{target_name}();")
                else:
                    # Process fault path normally
                    target_element = None
                    for element_type, elements in element_map.items():
                        if isinstance(elements, dict) and target_name in elements:
                            target_element = elements[target_name]
                            break
                    if target_element is not None:
                        if target_name in self.goto_targets and target_name in self.goto_methods:
                            self.line_builder.add(f"{target_name}();")
                        else:
                            self.process_chain(target_element, namespace, element_map, element)
            
            self.line_builder.end_block()
            self.line_builder.add("}")

    def find_element_by_name(self, target_name: str, element_map: FlowElementMap) -> Optional[ET.Element]:
        """
        Search all element type dictionaries in element_map for the given name.
        Returns the element if found, else None.
        """
        self.logger.debug(f"Searching for element by name: {target_name}")
        for element_type, elements in element_map.items():
            if isinstance(elements, dict) and target_name in elements:
                self.logger.debug(f"Found element in type: {element_type}")
                return elements[target_name]
        self.logger.debug("Element not found")
        return None
    
    def _process_paths(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process the paths of a decision or loop element.
        
        Args:
            element: The decision or loop element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
        """
        self.logger.debug("Processing paths for decision/loop element")
        # Process each path
        for path in element.findall(f"{namespace}paths"):
            target_ref = path.find(f"{namespace}targetReference")
            if target_ref is not None and hasattr(target_ref, 'text'):
                target_name = target_ref.text
                self.logger.debug(f"Found path target: {target_name}")
                target_element = self.find_element_by_name(target_name, element_map)
                if target_element is not None:
                    # Increase indentation for the path
                    self.line_builder.begin_block()
                    try:
                        self.process_chain(target_element, namespace, element_map, element)
                    finally:
                        self.line_builder.end_block()
    
    def _process_next_connector(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process the next connector in the chain.
        
        Args:
            element: The current element
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
        """
        self.logger.debug("Processing next connector")
        # Find all connectors
        for connector in element.findall(f"{namespace}connector"):
            target_ref = connector.find(f"{namespace}targetReference")
            if target_ref is not None and hasattr(target_ref, 'text'):
                target_name = target_ref.text
                self.logger.debug(f"Found connector target: {target_name}")
                target_element = self.find_element_by_name(target_name, element_map)
                if target_element is not None:
                    # Increase indentation for the connector
                    self.line_builder.begin_block()
                    try:
                        self.process_chain(target_element, namespace, element_map, element)
                    finally:
                        self.line_builder.end_block()

    def _analyze_function_returns(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> list[str]:
        """
        Analyze what variables this function should return based on the elements it processes.
        
        Args:
            element: The starting element of the function
            namespace: XML namespace
            element_map: Element map for lookups
            
        Returns:
            List of variable names that should be returned
        """
        returns = []
        
        # For now, focus on record lookup elements which typically set output variables
        if element.tag.replace(namespace, '') == 'recordLookups':
            # Check for outputReference or outputAssignments
            output_ref = element.find(f"{namespace}outputReference")
            if output_ref is not None and hasattr(output_ref, 'text'):
                returns.append(output_ref.text)
            
            # Check for outputAssignments
            for assignment in element.findall(f"{namespace}outputAssignments"):
                assign_to = assignment.find(f"{namespace}assignToReference")
                if assign_to is not None and hasattr(assign_to, 'text'):
                    returns.append(assign_to.text)
        
        # TODO: Add more element types (assignments, formulas, etc.)
        
        return returns
