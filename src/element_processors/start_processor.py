"""
Processor for Flow start elements.
"""
import logging
from typing import Optional, Tuple, List, Dict
import xml.etree.ElementTree as ET

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap
from utils.operator_formatter import FlowOperatorFormatter


class StartProcessor(BaseElementProcessor):
    """
    Processor for Flow start elements.
    
    This processor handles the conversion of Flow start elements into Apex-like
    trigger context. It processes the initial record, filters, and sets up the
    execution context.
    """
    
    def __init__(self, line_builder, variable_tracker, element_chain_processor):
        """
        Initialize the start processor.
        
        Args:
            line_builder: LineBuilder instance for generating output
            variable_tracker: FlowVariableTracker instance for tracking variables
            element_chain_processor: ElementChainProcessor instance for processing element chains
        """
        super().__init__(line_builder, variable_tracker)
        self.operator_formatter = FlowOperatorFormatter()
        self.element_chain_processor = element_chain_processor
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a start element and generate pseudocode.
        
        Args:
            element: The start element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
        """
        object_name = self._get_object_type(element, namespace)
        
        # Add method call first
        self.line_builder.add("processFlow();")
        
        # Then add method definition
        self.line_builder.new_method("processFlow")
        self._setup_trigger_context(object_name)
        
        # Process filters and chain
        filter_condition = self._process_filters(element, namespace)
        target_element = self._find_target_element(element, namespace, element_map)
        
        if filter_condition:
            self.line_builder.add(f"if ({filter_condition}) {{")
            self.line_builder.begin_block()
            
            if target_element is not None:
                self.element_chain_processor.process_chain(target_element, namespace, element_map)
            else:
                self.line_builder.add("// Continue flow processing")
            
            self.line_builder.end_block()
            self.line_builder.add("}")
        elif target_element is not None:
            self.element_chain_processor.process_chain(target_element, namespace, element_map)
        
        self.line_builder.end_method()
    
    def _get_object_type(self, element: ET.Element, namespace: str) -> str:
        """Get the object type from the start element."""
        object_type = element.find(f"{namespace}object")
        return object_type.text if object_type is not None and hasattr(object_type, 'text') else "SObject"
    
    def _setup_trigger_context(self, object_name: str) -> None:
        """Set up trigger context variables."""
        self.line_builder.add(f"{object_name} record = Trigger.new[0];")
        self.line_builder.add(f"{object_name} oldRecord = Trigger.old[0];")
        self.line_builder.add_blank()
    
    def _find_target_element(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> Optional[ET.Element]:
        """Find the target element from the connector or scheduledPaths."""
        # First try direct connector
        connector = element.find(f"{namespace}connector")
        if connector is not None:
            target_ref = connector.find(f"{namespace}targetReference")
            if target_ref is not None and hasattr(target_ref, 'text'):
                for element_type, elements in element_map.items():
                    if isinstance(elements, dict) and target_ref.text in elements:
                        return elements[target_ref.text]
        
        # If no direct connector, try scheduledPaths (for async flows)
        scheduled_paths = element.findall(f"{namespace}scheduledPaths")
        for path in scheduled_paths:
            path_connector = path.find(f"{namespace}connector")
            if path_connector is not None:
                target_ref = path_connector.find(f"{namespace}targetReference")
                if target_ref is not None and hasattr(target_ref, 'text'):
                    for element_type, elements in element_map.items():
                        if isinstance(elements, dict) and target_ref.text in elements:
                            return elements[target_ref.text]
        
        return None
    
    def _process_filters(self, element: ET.Element, namespace: str) -> Optional[str]:
        """
        Process filters from start element and return condition text if any.
        
        Args:
            element: The start element to process
            namespace: XML namespace
            
        Returns:
            Formatted condition string if filters exist, None otherwise
        """
        filters = element.findall(f"{namespace}filters")
        if not filters:
            return None

        filter_logic = element.find(f"{namespace}filterLogic")
        logic_operator = "&&" if filter_logic is None or filter_logic.text == "and" else "||"
        
        conditions = []
        for filter_elem in filters:
            field = filter_elem.find(f"{namespace}field")
            operator = filter_elem.find(f"{namespace}operator")
            
            if not all(elem is not None and hasattr(elem, 'text') for elem in [field, operator]):
                continue
                
            # Try to find stringValue directly under filters first
            string_value = filter_elem.find(f"{namespace}stringValue")
            if string_value is not None and hasattr(string_value, 'text'):
                condition = self.operator_formatter.format_condition(f"record.{field.text}", operator.text, f"'{string_value.text}'")
                conditions.append(condition)
                continue
            
            # If not found, try to find it under value element
            value = filter_elem.find(f"{namespace}value")
            if value is not None:
                string_value = value.find(f"{namespace}stringValue")
                boolean_value = value.find(f"{namespace}booleanValue")
                
                if string_value is not None and hasattr(string_value, 'text'):
                    condition = self.operator_formatter.format_condition(f"record.{field.text}", operator.text, f"'{string_value.text}'")
                    conditions.append(condition)
                elif boolean_value is not None and hasattr(boolean_value, 'text'):
                    condition = self.operator_formatter.format_condition(f"record.{field.text}", operator.text, boolean_value.text.lower())
                    conditions.append(condition)
                elif hasattr(value, 'text'):
                    condition = self.operator_formatter.format_condition(f"record.{field.text}", operator.text, value.text)
                    conditions.append(condition)
            else:
                # Handle special cases like IsChanged that don't have values
                if operator.text == "IsChanged":
                    conditions.append(f"record.{field.text} != oldRecord.{field.text}")
                else:
                    condition = self.operator_formatter.format_condition(f"record.{field.text}", operator.text, "true")
                    conditions.append(condition)
        
        return f" {logic_operator} ".join(conditions) if conditions else None
