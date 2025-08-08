"""
Main entry point for Flow transpilation service.
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Type

import xml.etree.ElementTree as ET
from element_processors.base_processor import BaseElementProcessor
from element_processors.action_processor import ActionProcessor
from element_processors.decision_processor import DecisionProcessor
from element_processors.loop_processor import LoopProcessor
from element_processors.subflow_processor import SubflowProcessor
from element_processors.element_chain_processor import ElementChainProcessor
from element_processors.screen_processor import ScreenProcessor
from models.flow_element_map import FlowElementMap
from utils.line_builder import LineBuilder
from utils.indentation_manager import IndentationManager
from utils.variable_tracker import FlowVariableTracker
from utils.operator_formatter import FlowOperatorFormatter
from element_processors.record_lookup_processor import RecordLookupProcessor
from element_processors.record_update_processor import RecordUpdateProcessor
from element_processors.record_create_processor import RecordCreateProcessor
from element_processors.start_processor import StartProcessor
from element_processors.record_processor import AssignmentProcessor
from element_processors.formula_processor import FormulaProcessor

# Configure logging to see the output
logging.basicConfig(
    level=logging.INFO,  # or logging.DEBUG for more detailed output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class FileSystemStorage:
    """Stub storage class with async read_file for minimal file reading."""
    async def read_file(self, file_path):
        # Defensive: ensure file_path is a Path object
        from pathlib import Path
        if not isinstance(file_path, Path):
            raise TypeError("file_path must be a pathlib.Path")
        return file_path.read_text(encoding="utf-8")

class FlowTranspilerService:
    """
    Main service for transpiling Salesforce Flow XML into Apex-like pseudocode.
    
    This class serves as the entry point for both CLI usage and programmatic access.
    It orchestrates the transpilation process using the various processors and utilities.
    """
    
    def __init__(self, storage: FileSystemStorage):
        """
        Initialize the flow transpiler service.
        
        Args:
            storage: File system storage service for accessing files
        """
        self.storage = storage
        self.processed_elements = set()  # Track elements we've already processed
        self.line_builder = LineBuilder(IndentationManager())  # This will be the only instance
        self.variable_tracker = FlowVariableTracker()
        self.operator_formatter = FlowOperatorFormatter()
        
        # Create a temporary element chain processor
        self.element_chain_processor = ElementChainProcessor({}, self.line_builder, self.variable_tracker)
        
        # Initialize processors
        self._initialize_processors()
        
        # Update element chain processor with the processors
        self.element_chain_processor.processors = self.processors
    
    def _initialize_processors(self) -> None:
        """Initialize all element processors."""
        self.formula_processor = FormulaProcessor(self.line_builder, self.variable_tracker)
        self.processors: Dict[str, BaseElementProcessor] = {
            'start': StartProcessor(self.line_builder, self.variable_tracker, self.element_chain_processor),
            'actionCalls': ActionProcessor(self.line_builder, self.variable_tracker),
            'decisions': DecisionProcessor(self.line_builder, self.variable_tracker, self.element_chain_processor),
            'loops': LoopProcessor(self.line_builder, self.variable_tracker, self.element_chain_processor),
            'subflows': SubflowProcessor(self.line_builder, self.variable_tracker),
            'recordLookups': RecordLookupProcessor(self.line_builder, self.variable_tracker),
            'recordUpdates': RecordUpdateProcessor(self.line_builder, self.variable_tracker),
            'recordCreates': RecordCreateProcessor(self.line_builder, self.variable_tracker),
            'assignments': AssignmentProcessor(self.line_builder, self.variable_tracker, self.formula_processor, self.element_chain_processor),
            'formulas': self.formula_processor,
            'screens': ScreenProcessor(self.line_builder, self.variable_tracker)
        }
    
    def _update_variable_tracker_references(self):
        """Update all processors to use the current variable_tracker instance."""
        for processor in self.processors.values():
            if hasattr(processor, 'variable_tracker'):
                processor.variable_tracker = self.variable_tracker
        if hasattr(self.element_chain_processor, 'variable_tracker'):
            self.element_chain_processor.variable_tracker = self.variable_tracker
    
    async def transpile_flow(self, flow_file: Path) -> str:
        """
        Transpile a Flow XML file to Apex-like pseudocode.
        
        Args:
            flow_file: Path to the Flow XML file
            
        Returns:
            Generated pseudocode as a string
        """
        # Read and parse the flow XML
        root, namespace = await self._read_and_parse_flow(flow_file)
        
        # Reset state for new transpilation
        self._reset_state()
        
        # Add flow header and metadata
        self._add_flow_header(root, namespace)
        
        # Process variables
        self._process_variables(root, namespace)
        
        # Process the flow elements
        self._process_flow_elements(root, namespace)
        
        # Return the formatted pseudocode
        result = "\n".join(self.line_builder.get_formatted_lines())
        print(f"Generated {len(result.splitlines())} lines of pseudocode")
        return result
        
    async def _read_and_parse_flow(self, flow_file: Path) -> tuple[ET.Element, str]:
        """
        Read and parse the flow XML file.
        
        Args:
            flow_file: Path to the Flow XML file
            
        Returns:
            Tuple of (root element, namespace)
        """
        flow_xml = await self.storage.read_file(flow_file)
        root = ET.fromstring(flow_xml)
        namespace = root.tag.split('}')[0] + '}' if '}' in root.tag else ''
        return root, namespace
        
    def _reset_state(self) -> None:
        """Reset all state for a new transpilation."""
        self.processed_elements = set()
        self.element_chain_processor.reset()
        self.line_builder.reset()
        self.variable_tracker = FlowVariableTracker()
        self._initialize_processors()
        
    def _add_flow_header(self, root: ET.Element, namespace: str) -> None:
        """
        Add flow header and metadata to the output.
        
        Args:
            root: Root element of the flow XML
            namespace: XML namespace
        """
        label = root.find(f"{namespace}label").text
        process_type = root.find(f"{namespace}processType").text
        status = root.find(f"{namespace}status").text
        description = root.find(f"{namespace}description").text if root.find(f"{namespace}description") is not None else ""
        
        self.line_builder.add_comment(f"Flow: {label}")
        self.line_builder.add_comment(f"Type: {self._map_flow_type(process_type)}")
        self.line_builder.add_comment(f"Status: {status}")
        if description:
            self.line_builder.add_comment(f"Description:\n//   {description}")
        self.line_builder.add_blank()
        
    def _process_variables(self, root: ET.Element, namespace: str) -> None:
        """
        Process and add variable declarations to the output.
        
        Args:
            root: Root element of the flow XML
            namespace: XML namespace
        """
        variables = root.findall(f"{namespace}variables")
        if not variables:
            return
            
        self.line_builder.add_comment("Variable Declarations")
        for var in variables:
            name = var.find(f"{namespace}name").text
            data_type = var.find(f"{namespace}dataType").text
            is_collection = var.find(f"{namespace}isCollection").text.lower() == "true"
            object_type = var.find(f"{namespace}objectType").text if var.find(f"{namespace}objectType") is not None else None
            
            # Build the type declaration
            if data_type == "SObject" and object_type:
                type_name = f"List<{object_type}>" if is_collection else object_type
            else:
                type_name = f"List<{data_type}>" if is_collection else data_type
            
            # Initialize collections as empty lists
            if is_collection:
                self.line_builder.add(f"{type_name} {name} = new {type_name}();")
            else:
                self.line_builder.add(f"{type_name} {name};")
        self.line_builder.add_blank()
        
    def _process_flow_elements(self, root: ET.Element, namespace: str) -> None:
        """
        Process all flow elements and generate pseudocode.
        
        Args:
            root: Root element of the flow XML
            namespace: XML namespace
        """
        # Map elements by name for easy reference
        element_map = self._build_element_map(root, namespace)
        
        # Scan for goto targets before processing
        self.element_chain_processor.scan_for_goto_targets(element_map, namespace)
        
        # Process start element
        start = root.find(f"{namespace}start")
        processor = self.processors.get('start')
        if processor:
            processor.process(start, namespace, element_map)
        else:
            print("No processor found for start element")
    
    def _build_element_map(self, root: ET.Element, namespace: str) -> FlowElementMap:
        """
        Create a map of all named elements for easy lookup.
        
        Args:
            root: Root element of the flow XML
            namespace: XML namespace
            
        Returns:
            Dictionary mapping element names to elements, organized by type
        """
        element_map: FlowElementMap = {
            'start': None,
            'decisions': {},
            'recordUpdates': {},
            'formulas': {},
            'recordLookups': {},
            'assignments': {},
            'actionCalls': {},
            'recordCreates': {},
            'loops': {},
            'screens': {},
            'textTemplates': {},
            'variables': {},
            'subflows': {}
        }
        
        # Process each element type
        for element_type in element_map.keys():
            # Find all elements of this type
            for element in root.findall(f"{namespace}{element_type}"):
                name_elem = element.find(f"{namespace}n") or element.find(f"{namespace}name")
                if name_elem is not None and hasattr(name_elem, 'text'):
                    element_map[element_type][name_elem.text] = element

        return element_map
    
    def _extract_flow_info(self, root: ET.Element, namespace: str) -> Dict[str, str]:
        """
        Extract basic information about the flow.
        
        Args:
            root: Root element of the flow XML
            namespace: XML namespace
            
        Returns:
            Dictionary containing flow information
        """
        info = {
            'label': 'Unknown Flow',
            'type': 'Unknown',
            'status': 'Unknown',
            'description': ''
        }
        
        label = root.find(f"{namespace}label")
        if label is not None and hasattr(label, 'text'):
            info['label'] = label.text
            
        process_type = root.find(f"{namespace}processType")
        if process_type is not None and hasattr(process_type, 'text'):
            info['type'] = self._map_flow_type(process_type.text)
            
        status = root.find(f"{namespace}status")
        if status is not None and hasattr(status, 'text'):
            info['status'] = status.text
            
        description = root.find(f"{namespace}description")
        if description is not None and hasattr(description, 'text'):
            info['description'] = description.text
            
        return info
    
    def _map_flow_type(self, process_type: str) -> str:
        """
        Map processType to more descriptive type.
        
        Args:
            process_type: The process type from the flow XML
            
        Returns:
            Mapped flow type
        """
        mapping = {
            'AutoLaunchedFlow': 'Autolaunched Flow',
            'Flow': 'Screen Flow',
            'Workflow': 'Workflow',
            'RoutingFlow': 'Service Routing Flow',
            'InvocableProcess': 'Process Builder',
            'CustomEvent': 'Platform Event Flow',
            'ContactRequest': 'Contact Request Flow',
            'LoginFlow': 'Login Flow',
            'Survey': 'Survey',
            'SurveyResponse': 'Survey Response Flow'
        }
        return mapping.get(process_type, process_type)
    
    def _add_flow_info_comments(self, flow_info: Dict[str, str]) -> None:
        """
        Add flow metadata as comments to the output.
        
        Args:
            flow_info: Dictionary containing flow information
        """
        self.line_builder.add_comment(f"Flow: {flow_info['label']}")
        self.line_builder.add_comment(f"Type: {flow_info['type']}")
        self.line_builder.add_comment(f"Status: {flow_info['status']}")
        if flow_info['description']:
            self.line_builder.add_comment("Description:")
            for line in flow_info['description'].split('\n'):
                self.line_builder.add_comment(f"  {line.strip()}")
        self.line_builder.add_blank()
    
    def _process_start_filters(self, start: ET.Element, namespace: str) -> Optional[str]:
        """
        Process filters from start element and return condition text if any.
        
        Args:
            start: The start element to process
            namespace: XML namespace
            
        Returns:
            Condition text if filters exist, None otherwise
        """
        filters = start.findall(f"{namespace}filters")
        if not filters:
            return None
        
        filter_logic = start.find(f"{namespace}filterLogic")
        logic_operator = filter_logic.text if filter_logic is not None and hasattr(filter_logic, 'text') else "and"
        
        conditions = []
        for filter_elem in filters:
            field = filter_elem.find(f"{namespace}field")
            operator = filter_elem.find(f"{namespace}operator")
            value = filter_elem.find(f".//{namespace}stringValue")
            if all(elem is not None and hasattr(elem, 'text') for elem in [field, operator, value]):
                operator_text = self.operator_formatter.format_operator(operator.text)
                if operator_text == '.contains':
                    conditions.append(f"record.{field.text}.contains('{value.text}')")
                else:
                    conditions.append(f"record.{field.text} {operator_text} '{value.text}'")
        
        return f" {logic_operator} ".join(conditions) if conditions else None


async def main():
    """CLI entry point for the flow transpiler using argparse."""
    parser = argparse.ArgumentParser(
        description="Transpile a Salesforce Flow XML file into Apex-like pseudocode."
    )
    parser.add_argument(
        "flow_file",
        type=str,
        help="Path to the Flow XML file to transpile"
    )
    args = parser.parse_args()
    storage = FileSystemStorage()
    transpiler = FlowTranspilerService(storage)
    flow_file = Path(args.flow_file)

    try:
        pseudocode = await transpiler.transpile_flow(flow_file)
        print(pseudocode)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
