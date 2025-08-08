"""
Processor for Flow assignment elements.
"""
import logging
from typing import Dict, Optional
import xml.etree.ElementTree as ET

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap


class AssignmentProcessor(BaseElementProcessor):
    """
    Processor for Flow assignment elements.
    
    This processor handles the conversion of Flow assignment elements into Apex-like
    assignment statements. It processes variable assignments, field updates, and
    collection operations.
    """
    
    def __init__(self, line_builder, variable_tracker, formula_processor, element_chain_processor):
        """
        Initialize the assignment processor.
        
        Args:
            line_builder: LineBuilder instance for generating output
            variable_tracker: FlowVariableTracker instance for tracking variables
            formula_processor: FormulaProcessor instance for processing formulas
            element_chain_processor: ElementChainProcessor instance for processing element chains
        """
        super().__init__(line_builder, variable_tracker)
        self.formula_processor = formula_processor
        self.element_chain_processor = element_chain_processor
        self.logger = logging.getLogger(__name__)
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process an assignment element and generate pseudocode.
        Loops through all assignment items and delegates processing.
        """
        name = self._get_assignment_name(element, namespace)
        for item in element.findall(f"{namespace}assignmentItems"):
            self._process_assignment_item(item, namespace)

    def _get_assignment_name(self, element: ET.Element, namespace: str) -> str:
        """
        Extract the assignment element's name for use in comments or debugging.
        """
        name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
        return name_elem.text if name_elem is not None and hasattr(name_elem, 'text') else "unnamed"

    def _process_assignment_item(self, item: ET.Element, namespace: str) -> None:
        """
        Process a single assignment item, resolving the target and value, and emit the assignment line.
        Handles special cases for record, loop, and collection references.
        """
        self.logger.debug(f"Assignment item children: {[child.tag for child in item]}")
        assign_to = item.find(f"{namespace}assignToReference")
        if assign_to is None:
            assign_to = item.find("assignToReference")
        if assign_to is not None and hasattr(assign_to, 'text'):
            target = assign_to.text
            self.logger.debug(f"Processing target reference: {target}")
            # Handle $Record. references
            if target.startswith('$Record.'):
                target = f"record.{target[8:]}"
                self.logger.debug(f"Converted record reference to: {target}")
            # Handle $Loop. references
            elif target.startswith('$Loop.'):
                loop_var = self.element_chain_processor.get_current_loop_var()
                if loop_var is not None:
                    target = f"{loop_var}.{target[6:]}"
                    self.logger.debug(f"Converted loop reference to: {target}")
                else:
                    self.logger.error(f"No loop variable found for {target}")
                    self.line_builder.add_comment(f"ERROR: No loop variable found for {target}")
                    return
            # Handle collection references (e.g., Linked_Leads.)
            elif target.startswith('Linked_Leads.'):
                loop_var = self.element_chain_processor.get_current_loop_var()
                if loop_var is not None:
                    target = f"{loop_var}.{target[12:]}"
                    self.logger.debug(f"Converted collection reference to: {target}")
                else:
                    self.logger.error(f"No loop variable found for {target}")
                    self.line_builder.add_comment(f"ERROR: No loop variable found for {target}")
                    return
            # Extract the value to assign
            value = self._extract_value(item, namespace)
            if value == "unknown":
                value = self._extract_value(item, "")
            self.logger.debug(f"Extracted value: {value}")
            # Emit the assignment line
            self.line_builder.add(f"{target} = {value};")

    def _extract_value(self, item: ET.Element, namespace: str) -> str:
        """
        Orchestrate value extraction for an assignment item.
        Tries element reference, string, boolean, and number in order.
        Returns 'unknown' if no value is found.
        """
        value = self._extract_element_reference_value(item, namespace)
        if value != "unknown":
            return value
        value = self._extract_string_value(item, namespace)
        if value != "unknown":
            return value
        value = self._extract_boolean_value(item, namespace)
        if value != "unknown":
            return value
        value = self._extract_number_value(item, namespace)
        if value != "unknown":
            return value
        self.logger.warning("No value found in assignment item")
        return "unknown"

    def _extract_element_reference_value(self, item: ET.Element, namespace: str) -> str:
        """
        Extract an element reference value (e.g., $Record., $Loop., or collection reference).
        Handles special cases for record, loop, and collection context.
        Returns 'unknown' if not found.
        """
        value_ref = item.find(f".//{namespace}elementReference")
        if value_ref is None:
            value_ref = item.find(".//elementReference")
        if value_ref is not None and hasattr(value_ref, 'text'):
            value = value_ref.text
            self.logger.debug(f"Found element reference: {value}")
            # $Record. reference
            if value.startswith('$Record.'):
                result = f"record.{value[8:]}"
                self.logger.debug(f"Converted record reference to: {result}")
                return result
            # $Loop. reference
            elif value.startswith('$Loop.'):
                loop_var = self.element_chain_processor.get_current_loop_var()
                if loop_var is not None:
                    result = f"{loop_var}.{value[6:]}"
                    self.logger.debug(f"Converted loop reference to: {result}")
                    return result
                else:
                    self.logger.error(f"No loop variable found for {value}")
                    self.line_builder.add_comment(f"ERROR: No loop variable found for {value}")
                    return "unknown"
            # Collection reference (e.g., Linked_Leads)
            elif value.startswith('Linked_Leads'):
                loop_var = self.element_chain_processor.get_current_loop_var()
                if loop_var is not None:
                    result = f"{loop_var}"
                    self.logger.debug(f"Converted collection reference to: {result}")
                    return result
                else:
                    self.logger.error(f"No loop variable found for {value}")
                    self.line_builder.add_comment(f"ERROR: No loop variable found for {value}")
                    return "unknown"
            return value
        return "unknown"

    def _extract_string_value(self, item: ET.Element, namespace: str) -> str:
        """
        Extract a string literal value from the assignment item.
        Returns the value wrapped in single quotes, or 'unknown' if not found.
        """
        string_value = item.find(f".//{namespace}stringValue")
        if string_value is None:
            string_value = item.find(".//stringValue")
        if string_value is not None and hasattr(string_value, 'text'):
            result = f"'{string_value.text}'"
            self.logger.debug(f"Found string value: {result}")
            return result
        return "unknown"

    def _extract_boolean_value(self, item: ET.Element, namespace: str) -> str:
        """
        Extract a boolean value from the assignment item.
        Returns 'true' or 'false', or 'unknown' if not found.
        """
        boolean_value = item.find(f".//{namespace}booleanValue")
        if boolean_value is None:
            boolean_value = item.find(".//booleanValue")
        if boolean_value is not None and hasattr(boolean_value, 'text'):
            result = boolean_value.text.lower()
            self.logger.debug(f"Found boolean value: {result}")
            return result
        return "unknown"

    def _extract_number_value(self, item: ET.Element, namespace: str) -> str:
        """
        Extract a number value from the assignment item.
        Returns the number as a string, or 'unknown' if not found.
        """
        number_value = item.find(f".//{namespace}numberValue")
        if number_value is None:
            number_value = item.find(".//numberValue")
        if number_value is not None and hasattr(number_value, 'text'):
            result = number_value.text
            self.logger.debug(f"Found number value: {result}")
            return result
        return "unknown" 