# Tool invocation format

CRITICAL: Never output tool calls as JSON objects.
You MUST use only Anthropic-style XML tags for all tool invocations:

<write_to_file>
<path>path/to/file</path>
<content>
file content here
</content>
</write_to_file>

<read_file>
<path>path/to/file</path>
</read_file>

<execute_command>
<command>ls -la</command>
</execute_command>

JSON output is silently ignored. XML tags are the only format that executes.