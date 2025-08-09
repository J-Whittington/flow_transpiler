# Flow Transpiler CLI

A command-line tool for converting Salesforce Flow XML files into Apex-like pseudocode.

## Overview

This tool reads a Salesforce Flow definition (XML) and produces a readable pseudocode representation of the flow's logic.  
It’s intended for developers who want to quickly inspect or document Flows without opening them in Salesforce's visual editor.

## Requirements

- Python 3.8+

Example:

```bash
python -m flow_transpiler_cli ~/Downloads/MyFlow.flow-meta.xml
```

This will print the generated pseudocode to standard output.

## Error Handling

If an error occurs during transpilation (e.g., file not found, invalid XML),
an error message will be printed to standard error and the process will exit with status code `1`.

## Notes

* The script uses `argparse` for CLI argument parsing.
* `FileSystemStorage` handles reading the Flow XML file.
* `FlowTranspilerService` contains the logic to parse and convert the Flow into pseudocode.
* The tool is asynchronous (`async/await`), but can be run directly as shown above.



