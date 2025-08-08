"""
Base processor class for Flow element processing.
"""
import xml.etree.ElementTree as ET
from typing import Dict, Optional

from utils.line_builder import LineBuilder
from utils.variable_tracker import FlowVariableTracker
from utils.operator_formatter import FlowOperatorFormatter
from models import FlowElementMap


class BaseElementProcessor:
    """
    Abstract base class for all Flow element processors.
    
    This class defines the interface and common functionality that all element
    processors must implement. Each processor is responsible for converting a
    specific type of Flow element into Apex-like pseudocode.
    """
    
    def __init__(self, line_builder: LineBuilder, variable_tracker: FlowVariableTracker):
        """
        Initialize the base processor.
        
        Args:
            line_builder: Utility for building and managing output lines
            variable_tracker: Utility for tracking variable types and names
        """
        self.line_builder = line_builder
        self.variable_tracker = variable_tracker
        self.operator_formatter = FlowOperatorFormatter()
    
    def process(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a Flow element and generate pseudocode.
        
        Args:
            element: The XML element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
            
        Raises:
            ElementProcessingError: If the element cannot be processed
        """
        self._add_element_header(element, namespace)
        self._process_impl(element, namespace, element_map)
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Implementation of element processing. Subclasses must override this method.
        
        Args:
            element: The XML element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
        """
        raise NotImplementedError("Subclasses must implement _process_impl()")
    
    def _add_element_header(self, element: ET.Element, namespace: str) -> None:
        """
        Add header comments for the element being processed.
        
        Args:
            element: The XML element being processed
            namespace: XML namespace for element queries
        """
        # Only add headers if we're not in method-only mode, or if we're currently in a method
        if not self.line_builder.method_mode_only or self.line_builder.current_method:
            # Add blank line before element
            self.line_builder.add_blank()
            
            # Get element name and type
            element_name = self.get_element_name(element, namespace)
            element_type = element.tag.split('}')[-1]  # Remove namespace prefix
            
            # Get description if available
            description = None
            desc_elem = element.find(f"{namespace}description")
            if desc_elem is not None and hasattr(desc_elem, 'text'):
                description = desc_elem.text
            
            # Add header comments
            self.line_builder.add_comment(f"{element_name}")
            if description:
                self.line_builder.add_comment(f"Description: {description}")
    
    def get_element_name(self, element: ET.Element, namespace: str) -> str:
        """
        Get the name of an element from its XML representation.
        
        Args:
            element: The XML element to process
            namespace: XML namespace for element queries
            
        Returns:
            The name of the element, or 'unnamed' if no name is found
        """
        name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
        return name_elem.text if name_elem is not None and hasattr(name_elem, 'text') else "unnamed"
    
    def add_comment(self, comment: str) -> None:
        """
        Add a comment to the output.
        
        Args:
            comment: The comment text to add
        """
        self.line_builder.add_comment(comment)
    
    def add_section_header(self, section_type: str, label: Optional[str] = None) -> None:
        """
        Add a standard section header comment.
        
        Args:
            section_type: The type of section
            label: Optional label for the section
        """
        self.line_builder.add_section_header(section_type, label)
    
    def begin_block(self, opening_line: Optional[str] = None) -> None:
        """
        Begin a new indentation block with optional opening line.
        
        Args:
            opening_line: Optional line to add before the opening brace
        """
        if opening_line:
            self.line_builder.add(opening_line + " {")
        else:
            self.line_builder.add("{")
        self.line_builder.begin_block()
    
    def end_block(self, closing_line: Optional[str] = None) -> None:
        """
        End the current indentation block with optional closing line.
        
        Args:
            closing_line: Optional line to add after the closing brace
        """
        self.line_builder.end_block()
        self.line_builder.add("}")
        if closing_line:
            self.line_builder.add(closing_line)
    
    def add_line(self, line: str) -> None:
        """
        Add a line of code to the output.
        
        Args:
            line: The line of code to add
        """
        self.line_builder.add(line)
    
    def add_blank(self) -> None:
        """Add a blank line to the output."""
        self.line_builder.add_blank()
    
    def format_condition(self, left_value: str, operator: str, right_value: str) -> str:
        """
        Format a condition using the operator formatter.
        
        Args:
            left_value: The left side of the condition
            operator: The operator to use
            right_value: The right side of the condition
            
        Returns:
            Formatted condition string
        """
        return self.operator_formatter.format_condition(left_value, operator, right_value)
    
    def format_operator(self, operator: str) -> str:
        """
        Format an operator using the operator formatter.
        
        Args:
            operator: The operator to format
            
        Returns:
            Formatted operator string
        """
        return self.operator_formatter.format_operator(operator)


class ElementProcessingError(Exception):
    """
    Exception raised when processing a Flow element fails.
    
    This exception should be raised when a processor encounters an error
    that prevents it from properly processing an element.
    """
    
    def __init__(self, element_name: str, message: str):
        """
        Initialize the error.
        
        Args:
            element_name: The name of the element that failed to process
            message: A description of what went wrong
        """
        self.element_name = element_name
        self.message = message
        super().__init__(f"Error processing element '{element_name}': {message}")
