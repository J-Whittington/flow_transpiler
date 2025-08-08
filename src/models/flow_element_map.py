"""
Data models for Flow elements and their types.
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, TypedDict


class FlowElementMap(TypedDict):
    """
    Type definition for the element map structure.
    
    This TypedDict defines the structure of the element map used to track
    all Flow elements during transpilation. Each key represents a type of
    element, and the value is a dictionary mapping element names to their
    XML representations.
    """
    start: Optional[ET.Element]
    decisions: Dict[str, ET.Element]
    recordUpdates: Dict[str, ET.Element]
    formulas: Dict[str, ET.Element]
    recordLookups: Dict[str, ET.Element]
    assignments: Dict[str, ET.Element]
    actionCalls: Dict[str, ET.Element]
    recordCreates: Dict[str, ET.Element]
    loops: Dict[str, ET.Element]
    screens: Dict[str, ET.Element]
    textTemplates: Dict[str, ET.Element]
    variables: Dict[str, ET.Element]
    subflows: Dict[str, ET.Element]


class FlowElementType:
    """
    Constants for flow element types.
    
    This class provides constants and utility methods for working with
    different types of Flow elements. It helps maintain consistency in
    element type naming and provides fallback prefixes for unnamed elements.
    """
    
    # Element type constants
    DECISIONS = "decisions"
    RECORD_UPDATES = "recordUpdates"
    FORMULAS = "formulas"
    RECORD_LOOKUPS = "recordLookups"
    ASSIGNMENTS = "assignments"
    ACTION_CALLS = "actionCalls"
    RECORD_CREATES = "recordCreates"
    LOOPS = "loops"
    SCREENS = "screens"
    TEXT_TEMPLATES = "textTemplates"
    VARIABLES = "variables"
    SUBFLOWS = "subflows"

    @classmethod
    def get_all_types(cls) -> List[Tuple[str, str]]:
        """
        Get all element types with their fallback prefixes.
        
        Returns:
            List of tuples containing (element_type, fallback_prefix)
        """
        return [
            (cls.DECISIONS, "decision_"),
            (cls.RECORD_UPDATES, "update_"),
            (cls.FORMULAS, "formula_"),
            (cls.RECORD_LOOKUPS, "lookup_"),
            (cls.ASSIGNMENTS, "assignment_"),
            (cls.ACTION_CALLS, "action_"),
            (cls.RECORD_CREATES, "create_"),
            (cls.LOOPS, "loop_"),
            (cls.SCREENS, "screen_"),
            (cls.TEXT_TEMPLATES, "template_"),
            (cls.VARIABLES, "variable_"),
            (cls.SUBFLOWS, "subflow_")
        ]
    
    @classmethod
    def is_valid_type(cls, element_type: str) -> bool:
        """
        Check if a given element type is valid.
        
        Args:
            element_type: The element type to check
            
        Returns:
            True if the element type is valid, False otherwise
        """
        return element_type in [
            cls.DECISIONS,
            cls.RECORD_UPDATES,
            cls.FORMULAS,
            cls.RECORD_LOOKUPS,
            cls.ASSIGNMENTS,
            cls.ACTION_CALLS,
            cls.RECORD_CREATES,
            cls.LOOPS,
            cls.SCREENS,
            cls.TEXT_TEMPLATES,
            cls.VARIABLES,
            cls.SUBFLOWS
        ]
    
    @classmethod
    def get_fallback_prefix(cls, element_type: str) -> Optional[str]:
        """
        Get the fallback prefix for an element type.
        
        Args:
            element_type: The element type to get the prefix for
            
        Returns:
            The fallback prefix for the element type, or None if not found
        """
        for type_name, prefix in cls.get_all_types():
            if type_name == element_type:
                return prefix
        return None
