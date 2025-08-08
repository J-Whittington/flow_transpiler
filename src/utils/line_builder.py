"""
Class to manage building text lines for flow processing without mixing indentation logic.
"""
import logging
from typing import List, Optional, Dict

from utils.indentation_manager import IndentationManager


class LineBuilder:
    """Class to manage building text lines for flow processing without mixing indentation logic"""
    
    _instance: Optional['LineBuilder'] = None
    
    def __new__(cls, indentation_manager: IndentationManager):
        """
        Create or return the singleton instance.
        
        Args:
            indentation_manager: Manager for handling indentation levels
            
        Returns:
            The singleton LineBuilder instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, indentation_manager: IndentationManager):
        """
        Initialize the line builder if not already initialized.
        
        Args:
            indentation_manager: Manager for handling indentation levels
        """
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        self.indentation = indentation_manager
        self.lines = []
        self.indentation_levels = []  # Stack to track indentation levels
        self.indentation_level = 0
        self.formatted = False  # Flag to track if formatting has been applied
        self.current_method = None  # Current method being built
        self.method_stack = []  # Stack to track nested method calls (method_name, indentation_level)
        self.methods: Dict[str, List[str]] = {}  # Map of method names to their lines
        self.method_indentation_levels: Dict[str, List[int]] = {}  # Map of method names to their indentation levels
        self.method_mode_only = False  # Flag to enforce that all lines must go to methods
        self._initialized = True
        
    
    def reset(self):
        """
        Reset the line builder to its initial state.
        This is useful when starting a new flow transpilation.
        """
        self.lines = []
        self.indentation_levels = []
        self.indentation_level = 0
        self.formatted = False
        self.current_method = None
        self.method_stack = []  # Stack to track nested method calls (method_name, indentation_level)
        self.methods = {}
        self.method_indentation_levels = {}
        self.method_mode_only = False
        if hasattr(self, 'method_return_types'):
            self.method_return_types = {}
        self.indentation.reset()
    
    def add(self, line: str):
        """
        Add a raw line of text without indentation.
        
        Args:
            line: The line to add
            
        Returns:
            self for method chaining
            
        Raises:
            RuntimeError: If method_mode_only is True and no current method is set
        """
        # If we've already formatted, we need to reset
        self.formatted = False
        
        # If method_mode_only is True, enforce that all lines must go to methods
        if self.method_mode_only and not self.current_method:
            raise RuntimeError(f"Cannot add line '{line}' to main code after method mode has been enabled. All lines must be added within a method context.")
        
        # Store the current indentation level with this line
        if self.current_method:
            if self.current_method not in self.methods:
                self.methods[self.current_method] = []
                self.method_indentation_levels[self.current_method] = []
            self.methods[self.current_method].append(line)
            self.method_indentation_levels[self.current_method].append(self.indentation.level)
        else:
            self.lines.append(line)
            self.indentation_levels.append(self.indentation.level)
        return self
    
    def add_comment(self, comment: str):
        """
        Add a comment line (adds // prefix).
        
        Args:
            comment: The comment to add
            
        Returns:
            self for method chaining
        """
        self.add(f"// {comment}")
        return self
    
    def add_section_header(self, section_type: str, label: str = None):
        """
        Add a standard section header comment.
        
        Args:
            section_type: The type of section
            label: Optional label for the section
            
        Returns:
            self for method chaining
        """
        if label:
            self.add(f"// {section_type} - {label}")
        else:
            self.add(f"// {section_type}")
        return self
    
    def add_blank(self):
        """
        Add a blank line.
        
        Returns:
            self for method chaining
        """
        self.add("")
        return self
    
    def begin_block(self):
        """
        Begin a new indentation block, increasing the indentation level.
        
        Returns:
            self for method chaining
        """
        self.indentation.increase()
        return self
    
    def end_block(self):
        """
        End the current indentation block, decreasing the indentation level.
        
        Returns:
            self for method chaining
        """
        self.indentation.decrease()
        return self

    def new_method(self, method_name: str, return_type: str = None):
        """
        Start a new method with the given name and optional return type.
        
        Args:
            method_name: Name of the method to start
            return_type: Optional return type for the method (defaults to void)
            
        Returns:
            self for method chaining
        """
        self.logger.info(f"Creating new method: {method_name}")

        # Push current method onto stack if we have one
        if self.current_method is not None:
            self.method_stack.append((self.current_method, self.indentation.level))

        # Reset indentation level for the new method
        self.indentation.reset()
        
        # Enable method-only mode once the first method is created
        self.method_mode_only = True
        
        self.current_method = method_name
        
        # Only create new lists if method doesn't exist, otherwise append to existing
        if method_name not in self.methods:
            self.methods[method_name] = []
            self.method_indentation_levels[method_name] = []
        
        # Store the return type for later use in formatting (only if not already set)
        if not hasattr(self, 'method_return_types'):
            self.method_return_types = {}
        if method_name not in self.method_return_types:
            self.method_return_types[method_name] = return_type or "void"
        
        return self

    def end_method(self):
        """
        End the current method and return to the previous method on the stack.
        
        Returns:
            self for method chaining
        """
        self.logger.info(f"Ending method: {self.current_method}")
        
        # Pop the previous method from the stack
        if self.method_stack:
            self.current_method, previous_indentation_level = self.method_stack.pop()
            self.logger.info(f"Returning to method: {self.current_method}")
            self.indentation.level = previous_indentation_level
        else:
            self.current_method = None
            self.logger.info("No previous method, returning to main code")
        
        return self

    def get_formatted_lines(self) -> List[str]:
        """
        Get the lines with proper indentation applied.
        
        Returns:
            List of formatted lines
        """
        # If already formatted, return the formatted lines
        if self.formatted:
            return self.lines

        # Format main code
        main_lines = self.indentation.format_lines(self.lines, self.indentation_levels)
        
        # Format methods
        method_lines = []
        for method_name, lines in self.methods.items():
            # Get return type for this method
            return_type = getattr(self, 'method_return_types', {}).get(method_name, 'void')
            
            # Add method declaration with proper return type
            if return_type == 'void':
                method_lines.append(f"private void {method_name}() {{")
            else:
                method_lines.append(f"private {return_type} {method_name}() {{")
            
            # Format method body with proper indentation
            method_body = self.indentation.format_lines(lines, self.method_indentation_levels[method_name])
            # Add indentation to each line of the method body
            method_body = [f"    {line}" for line in method_body]
            method_lines.extend(method_body)
            
            # Add closing brace
            method_lines.append("}")
            method_lines.append("")  # Add blank line between methods

        # Combine main code and methods
        self.lines = main_lines + method_lines
        self.formatted = True
        return self.lines
