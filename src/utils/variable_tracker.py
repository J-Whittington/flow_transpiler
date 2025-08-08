"""
Utility class for tracking variables and their types throughout flow processing.
"""
from typing import Dict, Optional, Tuple


class FlowVariableTracker:
    """
    Tracks variables and their types throughout the flow processing.
    
    This class maintains a mapping of variable names to their types, which is
    essential for proper type handling in the generated Apex code.
    """
    
    def __init__(self):
        """Initialize the variable tracker with an empty variable map."""
        self.variables: Dict[str, str] = {}  # Maps variable name to type
        self.loop_mappings: Dict[str, str] = {}  # Maps loop name to loop variable name
        
    def add_variable(self, name: str, type_name: str) -> None:
        """
        Add a variable to the tracker.
        
        Args:
            name: Variable name
            type_name: Variable type name
        """
        self.variables[name] = type_name
        
    def add_loop_mapping(self, loop_name: str, loop_var: str) -> None:
        """
        Add a mapping between a loop name and its loop variable.
        
        Args:
            loop_name: Name of the loop element
            loop_var: Name of the loop variable
        """
        self.loop_mappings[loop_name] = loop_var
        
    def get_loop_variable(self, loop_name: str) -> Optional[str]:
        """
        Get the loop variable name for a loop.
        
        Args:
            loop_name: Name of the loop element
            
        Returns:
            Loop variable name if found, None otherwise
        """
        return self.loop_mappings.get(loop_name)
        
    def get_type(self, name: str) -> Optional[str]:
        """
        Get the type of a variable.
        
        Args:
            name: Variable name
            
        Returns:
            Type name if found, None otherwise
        """
        type_name = self.variables.get(name)
        return type_name
        
    def is_list(self, name: str) -> bool:
        """
        Check if a variable is a list type.
        
        Args:
            name: The name of the variable to check
            
        Returns:
            True if the variable is a list type, False otherwise
        """
        return name in self.variables and self.variables[name].startswith('List<')
    
    def is_set(self, name: str) -> bool:
        """
        Check if a variable is a set type.
        
        Args:
            name: The name of the variable to check
            
        Returns:
            True if the variable is a set type, False otherwise
        """
        return name in self.variables and self.variables[name].startswith('Set<')
    
    def is_map(self, name: str) -> bool:
        """
        Check if a variable is a map type.
        
        Args:
            name: The name of the variable to check
            
        Returns:
            True if the variable is a map type, False otherwise
        """
        return name in self.variables and self.variables[name].startswith('Map<')
    
    def get_collection_types(self, name: str) -> Optional[Tuple[str, str]]:
        """
        Get the key and value types for a collection variable.
        
        Args:
            name: The name of the variable to check
            
        Returns:
            Tuple of (key_type, value_type) for maps, or (None, value_type) for lists/sets,
            or None if not a collection type
        """
        if name not in self.variables:
            return None
            
        type_str = self.variables[name]
        
        if type_str.startswith('Map<'):
            # Extract types from Map<KeyType,ValueType>
            types = type_str[4:-1].split(',')
            if len(types) == 2:
                return (types[0].strip(), types[1].strip())
        elif type_str.startswith('List<') or type_str.startswith('Set<'):
            # Extract type from List<Type> or Set<Type>
            return (None, type_str[type_str.find('<')+1:-1].strip())
            
        return None
    
    def clear(self) -> None:
        """Clear all tracked variables."""
        self.variables.clear()
        self.loop_mappings.clear()
    
    def get_all_variables(self) -> Dict[str, str]:
        """
        Get all tracked variables and their types.
        
        Returns:
            Dictionary mapping variable names to their types
        """
        return self.variables.copy()

    def get_loop_name_for_var(self, loop_var: str) -> Optional[str]:
        """
        Get the loop name for a given loop variable.
        
        Args:
            loop_var: The loop variable name to look up
            
        Returns:
            The loop name if found, None otherwise
        """
        for loop_name, var_name in self.loop_mappings.items():
            if var_name == loop_var:
                return loop_name
        return None
