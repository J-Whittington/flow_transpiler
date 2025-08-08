"""
Processor for decision elements in Flow XML.
"""
import logging
from typing import Optional, Dict
import xml.etree.ElementTree as ET

from element_processors.base_processor import BaseElementProcessor
from models import FlowElementMap


class DecisionProcessor(BaseElementProcessor):
    """
    Processes decision elements in Flow XML.
    
    This processor handles decision elements, which are used to create branching
    logic in flows based on conditions.
    """
    
    def __init__(self, line_builder, variable_tracker, element_chain_processor):
        """
        Initialize the decision processor.
        
        Args:
            line_builder: Line builder for generating code
            variable_tracker: Variable tracker for managing flow variables
            element_chain_processor: Element chain processor for handling connected elements
        """
        super().__init__(line_builder, variable_tracker)
        self.element_chain_processor = element_chain_processor
        self.logger = logging.getLogger(__name__)
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a decision element and generate pseudocode.
        Delegates rule and default connector handling to helpers for clarity.
        """
        # Get decision name
        name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
        if name_elem is None or not hasattr(name_elem, 'text'):
            raise Exception("Error processing element 'decision': Missing required name element")
        decision_name = name_elem.text

        # Add decision header
        self.line_builder.add(f"// Decision - {decision_name}")

        # Process all rules
        rules = element.findall(f"{namespace}rules")
        first = True
        for i, rule in enumerate(rules):
            is_last_rule = (i == len(rules) - 1)
            self._process_rule(rule, namespace, element_map, first, is_last_rule)
            first = False

        # Process default outcome
        self._process_default_connector(element, namespace, element_map)

    def _process_rule(self, rule: ET.Element, namespace: str, element_map: FlowElementMap, is_first: bool, is_last_rule: bool) -> None:
        """
        Process a single decision rule, including its condition and connector.
        """
        condition = rule.find(f"./{namespace}conditions")
        if condition is None:
            return
        condition_text = self._process_condition(condition, namespace)
        prefix = "if" if is_first else "} else if"
        self.line_builder.add(f"{prefix} ({condition_text}) {{")
        self.line_builder.begin_block()
        # Process target
        connector = rule.find(f"{namespace}connector")
        if connector is not None:
            target_ref = connector.find(f"{namespace}targetReference")
            if target_ref is not None and hasattr(target_ref, 'text'):
                target_name = target_ref.text
                target_element = None
                for element_type, elements in element_map.items():
                    if isinstance(elements, dict) and target_name in elements:
                        target_element = elements[target_name]
                        break
                if target_element is not None:
                    self.element_chain_processor.process_chain(target_element, namespace, element_map, rule)
        self.line_builder.end_block()
        # Only add closing } if this is the last rule and there's no default connector
        # The default connector or final closing will be handled elsewhere

    def _process_default_connector(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process the default connector (else block) for a decision element.
        """
        default_connector = element.find(f"{namespace}defaultConnector")
        if default_connector is not None:
            target_ref = default_connector.find(f"{namespace}targetReference")
            if target_ref is not None and hasattr(target_ref, 'text'):
                target_name = target_ref.text
                target_element = None
                for element_type, elements in element_map.items():
                    if isinstance(elements, dict) and target_name in elements:
                        target_element = elements[target_name]
                        break
                
                # Only generate else block if we have a valid target element
                if target_element is not None:
                    # Store current state to check if content is added
                    current_method = self.line_builder.current_method
                    lines_before = len(self.line_builder.lines) if not current_method else len(self.line_builder.methods.get(current_method, []))
                    
                    # Process the target element first to see if it generates content
                    self.element_chain_processor.process_chain(target_element, namespace, element_map, element)
                    
                    lines_after = len(self.line_builder.lines) if not current_method else len(self.line_builder.methods.get(current_method, []))
                    
                    # Only add else block if content was actually generated
                    if lines_after > lines_before:
                        # Content was added, wrap it in else block
                        # We need to insert the "} else {" before the new content
                        if current_method:
                            method_lines = self.line_builder.methods[current_method]
                            # Insert "} else {" at the position before the new content
                            method_lines.insert(lines_before, "} else {")
                            self.line_builder.method_indentation_levels[current_method].insert(lines_before, self.line_builder.indentation.level)
                            # Add closing brace
                            self.line_builder.add("}")
                        else:
                            # Insert "} else {" before the new content
                            self.line_builder.lines.insert(lines_before, "} else {")
                            self.line_builder.indentation_levels.insert(lines_before, self.line_builder.indentation.level)
                            # Add closing brace
                            self.line_builder.add("}")
                    else:
                        # No content was added, just close the last if/else if
                        self.line_builder.add("}")
                else:
                    # No valid target, just close the last if/else if
                    self.line_builder.add("}")
            else:
                # No target reference, just close the last if/else if
                self.line_builder.add("}")
        else:
            # No else block, just close the last if/else if
            self.line_builder.add("}")

    def _process_condition(self, condition: ET.Element, namespace: str) -> str:
        """
        Process a decision condition and return the formatted condition text.
        
        Args:
            condition: The condition element to process
            namespace: XML namespace for element queries
            
        Returns:
            Formatted condition text
        """
        left = condition.find(f"{namespace}leftValueReference")
        left_value = left.text.replace('$Record.', 'record.') if left is not None and hasattr(left, 'text') else "unknown"
        
        operator = condition.find(f"{namespace}operator")
        operator_text = operator.text if operator is not None and hasattr(operator, 'text') else "=="
        
        right_value = self._extract_right_value(condition, namespace)
        
        # Use the operator formatter for consistent formatting
        return self.operator_formatter.format_condition(left_value, operator_text, right_value)
    
    def _extract_right_value(self, condition: ET.Element, namespace: str) -> str:
        """
        Extract the right value from a condition element.
        
        Args:
            condition: The condition element to process
            namespace: XML namespace for element queries
            
        Returns:
            Extracted right value
        """
        right_value_elem = condition.find(f"{namespace}rightValue")
        if right_value_elem is None:
            return "unknown"
            
        string_value = right_value_elem.find(f"{namespace}stringValue")
        boolean_value = right_value_elem.find(f"{namespace}booleanValue")
        
        if string_value is not None and hasattr(string_value, 'text'):
            return f"'{string_value.text}'"
        if boolean_value is not None and hasattr(boolean_value, 'text'):
            return boolean_value.text.lower()
        return "unknown"
    

