"""
Processor for Flow screen elements with comprehensive field metadata and navigation context.
"""
import logging
from typing import Optional, List, Dict, Tuple
import xml.etree.ElementTree as ET
import re

from element_processors.base_processor import BaseElementProcessor, ElementProcessingError
from models import FlowElementMap


class ScreenProcessor(BaseElementProcessor):
    """
    Processor for Flow screen elements with comprehensive metadata extraction.
    
    This processor handles the conversion of Flow screen elements into detailed Apex-like
    pseudocode including field validation, custom components, navigation context, 
    dependencies, help text, data flow tracking, layout sections, and UX indicators.
    """
    
    def _map_field_type(self, flow_type: str) -> str:
        """
        Map Flow field types to Apex types.
        
        Args:
            flow_type: The Flow field type
            
        Returns:
            The corresponding Apex type
        """
        type_mapping = {
            'Text': 'String',
            'TextArea': 'String',
            'Picklist': 'String',
            'MultiPicklist': 'String',
            'Number': 'Decimal',
            'Currency': 'Decimal',
            'Date': 'Date',
            'DateTime': 'DateTime',
            'Boolean': 'Boolean',
            'Email': 'String',
            'Phone': 'String',
            'URL': 'String',
            'Reference': 'Id',
            'RadioButtons': 'String',
            'Checkbox': 'Boolean',
            'LookupFilter': 'Id'
        }
        return type_mapping.get(flow_type, 'String')
    
    def process(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Override base process to skip adding element header since we generate our own format.
        
        Args:
            element: The XML element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
        """
        self._process_impl(element, namespace, element_map)
    
    def _process_impl(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """
        Process a screen element and generate comprehensive pseudocode.
        
        Args:
            element: The screen element to process
            namespace: XML namespace for element queries
            element_map: Map of element names to elements for reference resolution
            
        Raises:
            ElementProcessingError: If the screen cannot be processed
        """
        # Get screen name and label
        name_elem = element.find(f"{namespace}name")
        label_elem = element.find(f"{namespace}label")
        screen_name = name_elem.text if name_elem is not None else "UnknownScreen"
        screen_label = label_elem.text if label_elem is not None else screen_name
        
        # Add screen header with label if different from name
        if screen_label != screen_name:
            self.line_builder.add(f"// Screen: {screen_label}")
        
        # Generate screen instantiation with all enhancements
        self._generate_enhanced_screen_instantiation(element, namespace, screen_name, element_map)
        
        # Process inputs with enhanced context
        self._process_enhanced_inputs(element, namespace)
        
        # Process outputs with data flow tracking
        self._process_enhanced_outputs(element, namespace)
        
        # Add navigation context
        self._process_navigation_context(element, namespace, element_map)
    
    def _generate_enhanced_screen_instantiation(self, element: ET.Element, namespace: str, screen_name: str, element_map: FlowElementMap) -> None:
        """
        Generate comprehensive screen instantiation with all field metadata.
        
        Args:
            element: The screen element
            namespace: XML namespace
            screen_name: Name of the screen
            element_map: Element map for navigation context
        """
        fields = element.findall(f"{namespace}fields")
        if not fields:
            self.line_builder.add(f"Screen {screen_name} = new Screen();")
            return

        # Categorize fields by type
        display_text_fields = []
        input_fields = []
        component_fields = []
        
        for field in fields:
            field_type_elem = field.find(f"{namespace}fieldType")
            if field_type_elem is None:
                continue
                
            field_type = field_type_elem.text
            if field_type == "DisplayText":
                display_text_fields.append(field)
            elif field_type == "ComponentInstance":
                component_fields.append(field)
            else:
                input_fields.append(field)
        
        # Add screen instructions if present
        self._add_screen_instructions(element, namespace)
        
        # Start screen constructor
        self.line_builder.add(f"Screen {screen_name} = new Screen(")
        self.line_builder.begin_block()
        
        # Add display text messages
        if display_text_fields:
            self._process_display_text_fields(display_text_fields, namespace)
            if input_fields or component_fields:
                self.line_builder.add("")
        
        # Add custom components
        if component_fields:
            self._process_component_fields(component_fields, namespace)
            if input_fields:
                self.line_builder.add("")
        
        # Process input fields with full metadata
        if input_fields:
            self._process_enhanced_input_fields(input_fields, namespace)
        
        self.line_builder.end_block()
        self.line_builder.add(");")
        self.line_builder.add("")
    
    def _add_screen_instructions(self, element: ET.Element, namespace: str) -> None:
        """Add screen-level instructions or descriptions."""
        # Check for screen description or help text
        description = element.find(f"{namespace}description")
        if description is not None and description.text:
            self.line_builder.add(f"// Instructions: {description.text}")
    
    def _process_display_text_fields(self, fields: List[ET.Element], namespace: str) -> None:
        """Process DisplayText fields with enhanced message formatting."""
        for field in fields:
            field_text = field.find(f"{namespace}fieldText")
            if field_text is not None and field_text.text:
                message = self._clean_html_message(field_text.text)
                self.line_builder.add(f"// Message: {message}")
    
    def _process_component_fields(self, fields: List[ET.Element], namespace: str) -> None:
        """Process custom component fields with parameter details."""
        for field in fields:
            name_elem = field.find(f"{namespace}name")
            extension_elem = field.find(f"{namespace}extensionName")
            
            if name_elem is None:
                continue
                
            field_name = name_elem.text
            extension_name = extension_elem.text if extension_elem is not None else "Custom Component"
            
            self.line_builder.add(f"// {field_name} Component ({extension_name})")
            
            # Process component parameters
            params = field.findall(f"{namespace}inputParameters")
            if params:
                param_details = []
                for param in params:
                    param_name = param.find(f"{namespace}name")
                    param_value = param.find(f"{namespace}value")
                    
                    if param_name is not None and param_value is not None:
                        value_text = self._extract_parameter_value(param_value, namespace)
                        param_details.append(f"{param_name.text}: {value_text}")
                
                if param_details:
                    self.line_builder.add(f"// Parameters: {', '.join(param_details)}")
    
    def _process_enhanced_input_fields(self, fields: List[ET.Element], namespace: str) -> None:
        """Process input fields with comprehensive metadata."""
        # Group fields by sections if applicable
        sections = self._group_fields_by_section(fields)
        
        for section_name, section_fields in sections.items():
            if section_name and section_name != "default":
                self.line_builder.add(f"// === {section_name} ===")
            
            for i, field in enumerate(section_fields):
                is_last_overall = (section_name == list(sections.keys())[-1] and 
                                 i == len(section_fields) - 1)
                self._process_single_input_field(field, namespace, is_last_overall)
                
            if section_name and section_name != "default" and section_name != list(sections.keys())[-1]:
                self.line_builder.add("")
    
    def _group_fields_by_section(self, fields: List[ET.Element]) -> Dict[str, List[ET.Element]]:
        """Group fields by logical sections based on naming patterns."""
        sections = {"default": []}
        
        for field in fields:
            name_elem = field.find(f".//name")
            if name_elem is None:
                sections["default"].append(field)
                continue
                
            field_name = name_elem.text.lower()
            
            # Detect common sections based on field names
            if any(keyword in field_name for keyword in ['contact', 'phone', 'email']):
                if "Contact Information" not in sections:
                    sections["Contact Information"] = []
                sections["Contact Information"].append(field)
            elif any(keyword in field_name for keyword in ['account', 'company', 'organization']):
                if "Account Details" not in sections:
                    sections["Account Details"] = []
                sections["Account Details"].append(field)
            elif any(keyword in field_name for keyword in ['address', 'street', 'city', 'state', 'zip', 'country']):
                if "Address Information" not in sections:
                    sections["Address Information"] = []
                sections["Address Information"].append(field)
            else:
                sections["default"].append(field)
        
        # Remove empty default section
        if not sections["default"]:
            del sections["default"]
        
        return sections
    
    def _process_single_input_field(self, field: ET.Element, namespace: str, is_last: bool) -> None:
        """Process a single input field with full metadata."""
        name = field.find(f"{namespace}name")
        data_type = field.find(f"{namespace}dataType")
        field_text = field.find(f"{namespace}fieldText")
        field_type = field.find(f"{namespace}fieldType")
        is_required = field.find(f"{namespace}isRequired")
        default_value = field.find(f"{namespace}defaultValue")
        help_text = field.find(f"{namespace}helpText")
        
        if name is None:
            return
            
        field_name = name.text
        
        # Build comprehensive field comment
        comment_parts = []
        
        # Add field label and type
        if field_text is not None:
            comment_parts.append(field_text.text)
        
        # Add field type details
        type_info = self._get_field_type_info(field, namespace)
        if type_info:
            comment_parts.append(type_info)
        
        # Add requirement status
        required_text = "Required" if is_required is not None and is_required.text.lower() == "true" else "Optional"
        comment_parts.append(required_text)
        
        # Add default value - handle both simple text and nested structure
        if default_value is not None:
            if default_value.text:
                # Simple text default value
                comment_parts.append(f"Default: \"{default_value.text}\"")
            else:
                # Try to extract from nested structure
                default_text = self._extract_parameter_value(default_value, namespace)
                if default_text and default_text != "null":
                    comment_parts.append(f"Default: {default_text}")
        
        # Build the comment
        if comment_parts:
            self.line_builder.add(f"// {' - '.join(comment_parts)}")
        
        # Add help text if present
        if help_text is not None and help_text.text:
            self.line_builder.add(f"// Help: {help_text.text}")
        
        # Add validation rules
        validation_info = self._get_validation_info(field, namespace)
        if validation_info:
            self.line_builder.add(f"// Validation: {validation_info}")
        
        # Add the field parameter
        apex_type = self._map_field_type(data_type.text if data_type is not None else 'String')
        comma = "" if is_last else ","
        
        # Add conditional visibility note
        visibility_info = self._get_visibility_info(field, namespace)
        visibility_comment = f" // {visibility_info}" if visibility_info else " // User input field"
        
        self.line_builder.add(f"{apex_type} {field_name}{comma}{visibility_comment}")
    
    def _get_field_type_info(self, field: ET.Element, namespace: str) -> str:
        """Get detailed field type information including choices and constraints."""
        field_type = field.find(f"{namespace}fieldType")
        data_type = field.find(f"{namespace}dataType")
        
        if field_type is None:
            return ""
            
        type_text = field_type.text
        
        # Handle special field types
        if type_text == "RadioButtons":
            choices = self._get_choice_values(field, namespace)
            return f"Radio: {choices}" if choices else "Radio"
        elif type_text == "Picklist":
            choices = self._get_choice_values(field, namespace)  
            return f"Picklist: {choices}" if choices else "Picklist"
        elif type_text == "MultiPicklist":
            choices = self._get_choice_values(field, namespace)
            return f"MultiPicklist: {choices}" if choices else "MultiPicklist"
        elif type_text == "Checkbox":
            return "Checkbox"
        elif data_type is not None:
            dt = data_type.text
            if dt == "Email":
                return "Email format required"
            elif dt == "Phone":
                return "Phone format"
            elif dt == "URL":
                return "URL format"
            elif dt == "Currency":
                return "Currency"
            elif dt == "Date":
                return "Date"
            elif dt == "DateTime":
                return "DateTime"
            else:
                return dt
        
        return type_text if type_text else ""
    
    def _get_choice_values(self, field: ET.Element, namespace: str) -> str:
        """Extract choice values for radio buttons and picklists."""
        choices = []
        
        # Look for choice references
        choice_refs = field.findall(f"{namespace}choiceReferences")
        if choice_refs:
            for choice_ref in choice_refs:
                if choice_ref.text:
                    choices.append(f'"{choice_ref.text}"')
        
        # Look for static choices (less common)
        choice_elems = field.findall(f"{namespace}choices")
        for choice in choice_elems:
            name_elem = choice.find(f"{namespace}name")
            if name_elem is not None and name_elem.text:
                choices.append(f'"{name_elem.text}"')
        
        return f"[{', '.join(choices)}]" if choices else ""
    
    def _get_validation_info(self, field: ET.Element, namespace: str) -> str:
        """Extract field validation information."""
        validation_parts = []
        
        # Check for scale and precision (numbers)
        scale = field.find(f"{namespace}scale")
        if scale is not None and scale.text:
            validation_parts.append(f"Scale: {scale.text}")
            
        # Check for string length
        data_type = field.find(f"{namespace}dataType")
        if data_type is not None and data_type.text in ['Text', 'TextArea']:
            # Default lengths based on type
            if data_type.text == 'Text':
                validation_parts.append("Max length: 255")
            elif data_type.text == 'TextArea':
                validation_parts.append("Max length: 32,768")
        
        # Check for validation rules (if present in XML)
        validation_rule = field.find(f"{namespace}validationRule")
        if validation_rule is not None and validation_rule.text:
            validation_parts.append(f"Rule: {validation_rule.text}")
        
        return ", ".join(validation_parts) if validation_parts else ""
    
    def _get_visibility_info(self, field: ET.Element, namespace: str) -> str:
        """Get field visibility and conditional information."""
        # Check for visibility rules
        visibility_rule = field.find(f"{namespace}visibilityRule")
        if visibility_rule is not None and visibility_rule.text:
            return f"Visible when: {visibility_rule.text}"
        
        # Check for conditional display
        conditional = field.find(f"{namespace}inputsOnNextNavToAssocScrn")
        if conditional is not None and conditional.text == "ResetValues":
            return "Conditional field"
            
        return ""
    
    def _clean_html_message(self, message: str) -> str:
        """Clean HTML encoding from display text messages."""
        # Remove HTML tags
        message = re.sub(r'&lt;[^&]*&gt;', '', message)
        # Fix HTML entities
        message = message.replace('&quot;', '"')
        message = message.replace('&amp;', '&')
        message = message.replace('&lt;', '<')
        message = message.replace('&gt;', '>')
        # Handle Flow variables
        message = re.sub(r'\{!([^}]+)\}', r'{\1}', message)
        # Clean up extra spaces
        message = re.sub(r'\s+', ' ', message).strip()
        return message
    
    def _extract_parameter_value(self, value_elem: ET.Element, namespace: str) -> str:
        """Extract parameter value from various value types."""
        # Check for string value
        string_value = value_elem.find(f"{namespace}stringValue")
        if string_value is not None:
            return f'"{string_value.text}"'
            
        # Check for boolean value
        boolean_value = value_elem.find(f"{namespace}booleanValue")
        if boolean_value is not None:
            return boolean_value.text.lower()
            
        # Check for number value
        number_value = value_elem.find(f"{namespace}numberValue")
        if number_value is not None:
            return number_value.text
            
        # Check for element reference
        element_ref = value_elem.find(f"{namespace}elementReference")
        if element_ref is not None:
            return f"{{{element_ref.text}}}"
            
        return "null"
    
    def _process_enhanced_inputs(self, element: ET.Element, namespace: str) -> None:
        """Process screen input parameters with enhanced context."""
        inputs = element.findall(f"{namespace}inputParameters")
        if not inputs:
            return
            
        self.line_builder.add("// Screen Inputs (Pre-populated values):")
        for input_elem in inputs:
            name = input_elem.find(f"{namespace}name")
            value = input_elem.find(f"{namespace}value")
            
            if name is None or value is None:
                continue
                
            value_text = self._extract_parameter_value(value, namespace)
            self.line_builder.add(f"//    {name.text} = {value_text}")
        self.line_builder.add("")
    
    def _process_enhanced_outputs(self, element: ET.Element, namespace: str) -> None:
        """Process screen output assignments with data flow tracking."""
        outputs = element.findall(f"{namespace}outputParameters")
        if not outputs:
            return
            
        self.line_builder.add("// Screen Outputs (Data flow to next steps):")
        for output in outputs:
            name = output.find(f"{namespace}name")
            value = output.find(f"{namespace}value")
            
            if name is None or value is None:
                continue
                
            value_text = self._extract_parameter_value(value, namespace)
            self.line_builder.add(f"//    {name.text} = {value_text};")
        self.line_builder.add("")
    
    def _process_navigation_context(self, element: ET.Element, namespace: str, element_map: FlowElementMap) -> None:
        """Add navigation context showing where this screen leads."""
        connectors = []
        
        # Main connector (Next/Finish button)
        connector = element.find(f"{namespace}connector")
        if connector is not None:
            target_ref = connector.find(f"{namespace}targetReference")
            if target_ref is not None and target_ref.text:
                connectors.append(("Next/Finish", target_ref.text))
        
        # Fault connector (error handling)
        fault_connector = element.find(f"{namespace}faultConnector")
        if fault_connector is not None:
            target_ref = fault_connector.find(f"{namespace}targetReference")
            if target_ref is not None and target_ref.text:
                connectors.append(("On Error", target_ref.text))
        
        # Pause connector (if pausable)
        pause_connector = element.find(f"{namespace}pauseConnector")
        if pause_connector is not None:
            target_ref = pause_connector.find(f"{namespace}targetReference")
            if target_ref is not None and target_ref.text:
                connectors.append(("On Pause", target_ref.text))
        
        if connectors:
            self.line_builder.add("// Navigation:")
            for action, target in connectors:
                # Try to get target element type for better context
                target_element = element_map.get(target)
                target_type = ""
                if target_element is not None:
                    target_type = f" ({target_element.tag.split('}')[-1] if '}' in target_element.tag else target_element.tag})"
                
                self.line_builder.add(f"//    {action} -> {target}{target_type}")
            self.line_builder.add("")
    
    def _get_input_value(self, value_elem: ET.Element, namespace: str) -> str:
        """
        Get the input value from the value element.
        
        Args:
            value_elem: The value element
            namespace: The XML namespace
            
        Returns:
            The input value as a string
        """
        return self._extract_parameter_value(value_elem, namespace)
    
    def _get_output_value(self, value_elem: ET.Element, namespace: str) -> str:
        """
        Get the output value from the value element.
        
        Args:
            value_elem: The value element
            namespace: The XML namespace
            
        Returns:
            The output value as a string
        """
        return self._extract_parameter_value(value_elem, namespace)
