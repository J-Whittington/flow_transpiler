"""
Utility class for formatting flow operators to match Apex syntax.
"""
from typing import Dict


class FlowOperatorFormatter:
    """
    Utility class for formatting flow operators to match Apex syntax.
    
    This class handles the conversion of Flow's operator syntax to Apex-compatible
    operators. For example, converting 'EqualTo' to '==', 'Contains' to '.contains',
    etc.
    """
    
    # Mapping of Flow operators to Apex operators
    OPERATOR_MAP: Dict[str, str] = {
        'EqualTo': '==',
        'NotEqualTo': '!=',
        'GreaterThan': '>',
        'LessThan': '<',
        'GreaterThanOrEqualTo': '>=',
        'LessThanOrEqualTo': '<=',
        'Contains': '.contains',
        'StartsWith': '.startsWith',
        'EndsWith': '.endsWith',
        'Includes': '.contains',
        'Excludes': '!contains',
        'IsNull': '== null',
        'IsNotNull': '!= null',
        'IsChanged': '!=',  # Special handling for IsChanged
        'IsNew': '.isNew()',
        'IsDeleted': '.isDeleted()'
    }
    
    @classmethod
    def format_operator(cls, operator: str) -> str:
        """
        Format a flow operator to match Apex syntax.
        
        Args:
            operator: The flow operator to format (e.g., 'EqualTo', 'Contains')
            
        Returns:
            Formatted operator string (e.g., '==', '.contains')
        """
        return cls.OPERATOR_MAP.get(operator, operator)
    
    @classmethod
    def format_condition(cls, left_value: str, operator: str, right_value: str) -> str:
        """
        Format a complete condition with operator.
        
        Args:
            left_value: The left side of the condition
            operator: The operator to use
            right_value: The right side of the condition
            
        Returns:
            Formatted condition string
        """
        formatted_operator = cls.format_operator(operator)
        
        # Handle special cases
        if operator == 'IsNull':
            return f"{left_value} != null" if right_value == "false" else f"{left_value} == null"
        elif operator == 'IsChanged':
            # IsChanged compares current value to old value
            old_value = left_value.replace('record.', 'oldRecord.')
            return f"{left_value} != {old_value}"
        elif operator in ['IsNotNull']:
            return f"{left_value} {formatted_operator}"
        elif operator in ['IsNew', 'IsDeleted']:
            return f"{left_value}{formatted_operator}"
        elif operator in ['Contains', 'StartsWith', 'EndsWith', 'Includes', 'Excludes']:
            return f"{left_value}{formatted_operator}({right_value})"
        else:
            return f"{left_value} {formatted_operator} {right_value}"
