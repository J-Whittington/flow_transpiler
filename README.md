# Flow Transpiler CLI

A command-line tool for converting Salesforce Flow XML files into Apex-like pseudocode.

## Overview

This tool reads a Salesforce Flow definition (XML) and produces a readable pseudocode representation of the flow's logic.  
It’s intended for developers who want to quickly inspect or document Flows without opening them in Salesforce's visual editor.

## Requirements

- Python 3.8+

Example:

```bash
python src/flow_transpiler_service.py ~/Downloads/MyFlow.flow-meta.xml
```

This will print the generated pseudocode to standard output.





