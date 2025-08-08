"""
Class to manage indentation levels throughout flow processing.
"""
from typing import List


class IndentationManager:
    """Class to manage indentation levels throughout flow processing"""
    
    def __init__(self, base_indent_str="    "):
        """
        Initialize the indentation manager.
        
        Args:
            base_indent_str: The string to use for each indentation level
        """
        self.indent_str = base_indent_str
        self.level = 0
        self.stack = []  # Track indentation history for complex nesting
        
    def increase(self, levels=1):
        """
        Increase indentation by specified number of levels.
        
        Args:
            levels: Number of levels to increase indentation
            
        Returns:
            Current indentation level
        """
        self.level += levels
        return self.level
    
    def decrease(self, levels=1):
        """
        Decrease indentation by specified number of levels.
        
        Args:
            levels: Number of levels to decrease indentation
            
        Returns:
            Current indentation level
        """
        self.level = max(0, self.level - levels)  # Prevent negative indentation
        return self.level
    
    def reset(self):
        """
        Reset indentation to 0.
        
        Returns:
            Current indentation level (0)
        """
        self.level = 0
        return self.level
    
    def set_level(self, level):
        """
        Set indentation to a specific level.
        
        Args:
            level: Target indentation level
            
        Returns:
            Current indentation level
        """
        self.level = max(0, level)
        return self.level
        
    def get_current(self):
        """
        Get current indentation string based on level.
        
        Returns:
            Current indentation string
        """
        return self.indent_str * self.level
    
    def push(self):
        """Save current indentation level to stack."""
        self.stack.append(self.level)
        
    def pop(self):
        """
        Restore indentation level from stack.
        
        Returns:
            Current indentation level
        """
        if self.stack:
            self.level = self.stack.pop()
        return self.level
        
    def format_lines(self, lines: List[str], indentation_levels: List[int]) -> List[str]:
        """
        Format a list of lines with their corresponding indentation levels.
        
        Args:
            lines: List of lines to format
            indentation_levels: List of indentation levels corresponding to each line
            
        Returns:
            List of formatted lines with proper indentation
        """
        formatted_lines = []
        for line, level in zip(lines, indentation_levels):
            if line.strip():  # Only add indentation to non-empty lines
                formatted_lines.append(self.indent_str * level + line)
            else:
                formatted_lines.append(line)
        return formatted_lines

    def format_complex_conditions(self, conditions: List[str]) -> str:
        """
        Format complex conditions with newlines and indentation.
        
        Args:
            conditions: List of condition strings to format
            
        Returns:
            Formatted condition string
        """
        if len(conditions) <= 1:
            return " && ".join(conditions) if conditions else "condition unknown"
            
        # For multiple conditions, format with newlines
        condition_indent = self.get_current() + self.indent_str
        operator_indent = condition_indent + self.indent_str
        
        # First condition on the same line
        result = conditions[0]
        
        # Remaining conditions with newlines and proper indentation
        for condition in conditions[1:]:
            result += f"\n{operator_indent}&& {condition}"
            
        return result
