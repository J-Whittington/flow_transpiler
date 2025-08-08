"""
Processor for Flow formula elements.
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap


class FormulaProcessor(BaseElementProcessor):
    """
    Processor for Flow formula elements.
    
    This processor handles the conversion of Flow formula elements into Apex-like
    expressions. It processes various formula types including CASE statements,
    arithmetic operations, and string concatenation.
    """
    
    def __init__(self, line_builder, variable_tracker):
        """Initialize the formula processor."""
        super().__init__(line_builder, variable_tracker)
        self.formula_functions = {}  # Track formula functions for later use
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a formula element and generate pseudocode.
        
        Args:
            element: The formula element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
            
        Raises:
            ElementProcessingError: If the formula cannot be processed
        """
        # Get formula name
        name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
        if name_elem is None or not hasattr(name_elem, 'text'):
            raise ElementProcessingError("formula", "Missing required name element")
        formula_name = name_elem.text
        
        # Get data type
        data_type = element.find(f"{namespace}dataType")
        if data_type is None or not hasattr(data_type, 'text'):
            raise ElementProcessingError("formula", "Missing required data type")
        type_name = data_type.text
        
        # Get expression
        expression = element.find(f"{namespace}expression")
        if expression is None or not hasattr(expression, 'text'):
            raise ElementProcessingError("formula", "Missing required expression")
        expr_text = expression.text
        
        # Track the variable and its type
        self.variable_tracker.add_variable(formula_name, type_name)
        
        # Process the expression
        processed_expr = self._process_expression(expr_text)
        
        # Generate the function
        function_name = f"get{formula_name}"
        self.line_builder.add(f"private static {type_name} {function_name}() {{")
        self.line_builder.begin_block()
        self.line_builder.add(f"return {processed_expr};")
        self.line_builder.end_block()
        self.line_builder.add("}")
        self.line_builder.add_blank()
        
        # Store the function name for later use
        self.formula_functions[formula_name] = function_name
    
    def get_formula_function(self, formula_name: str) -> str:
        """
        Get the function name for a formula.
        
        Args:
            formula_name: The name of the formula
            
        Returns:
            The function name to call
        """
        return self.formula_functions.get(formula_name, formula_name)
    
    def _process_expression(self, expression: str) -> str:
        """
        Process a formula expression and convert it to Apex syntax.
        
        Args:
            expression: The formula expression to process
            
        Returns:
            Processed expression in Apex syntax
        """
        # Handle CASE statements
        if expression.strip().startswith('CASE'):
            return self._process_case_statement(expression)
        
        # Handle basic expressions
        return self._process_basic_expression(expression)
    
    def _process_case_statement(self, expression: str) -> str:
        """
        Process a CASE statement and convert it to Apex syntax.
        
        Args:
            expression: The CASE statement to process
            
        Returns:
            Processed CASE statement in Apex syntax
        """
        # Remove the outer CASE and parentheses
        expr = expression.strip()[5:].strip()
        if expr.startswith('('):
            expr = expr[1:-1]
        
        # Split into parts
        parts = [p.strip() for p in expr.split(',')]
        
        # Process each part
        result = []
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                when_value = parts[i].strip()
                then_value = parts[i + 1].strip()
                
                # Handle special case for empty string
                if when_value == "''":
                    result.append(f"else {then_value}")
                else:
                    # Replace Flow merge syntax with Apex syntax
                    when_value = when_value.replace('{!', '').replace('}', '')
                    result.append(f"when {when_value} then {then_value}")
        
        # Join the parts and wrap in a switch statement
        return f"switch on {result[0]} {{\n" + \
               "\n".join(f"    {part}" for part in result[1:]) + \
               "\n}"
    
    def _process_basic_expression(self, expression: str) -> str:
        """
        Process a basic expression and convert it to Apex syntax.
        
        Args:
            expression: The expression to process
            
        Returns:
            Processed expression in Apex syntax
        """
        # Replace Flow merge syntax with Apex syntax
        return expression.replace('{!', '').replace('}', '')
