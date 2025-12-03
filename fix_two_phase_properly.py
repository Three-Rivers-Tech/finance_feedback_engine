#!/usr/bin/env python3
"""
Properly extract aggregate_decisions_two_phase from nested scope and make it a class method.
"""
import re

filepath = 'finance_feedback_engine/decision_engine/ensemble_manager.py'

with open(filepath, 'r') as f:
    content = f.read()

# Find the nested function definition and its body
# It starts after "return final_decision" in aggregate_decisions
# and is indented with 8 spaces (nested inside aggregate_decisions which has 4 spaces)

# Pattern: find "        def aggregate_decisions_two_phase(" (8 spaces + def)
# Replace with "    def aggregate_decisions_two_phase(" (4 spaces + def)
# And dedent all lines in its body from 12 spaces to 8 spaces

# First, let's find where aggregate_decisions ends (before the nested function)
# We'll split at "return final_decision" then look for the nested function

parts = content.split('        def aggregate_decisions_two_phase(', 1)
if len(parts) != 2:
    print("Could not find nested aggregate_decisions_two_phase")
    exit(1)

before = parts[0]
after_with_nested = parts[1]

# Now we need to dedent the entire nested function
# The signature line needs to go from 8 spaces to 4 spaces
# The body needs to go from 12 spaces to 8 spaces

# Find the end of this nested function (next def at same or lower indentation level)
# Since it's nested at 8 spaces, it ends when we see a line starting with 0-7 spaces followed by 'def'
# or when we see something at class level

lines = after_with_nested.split('\n')
fixed_lines = []

# The first line is the continuation of the signature
# "(self, prompt: str, ..." - keep as is, but we'll prepend the corrected def line
fixed_lines.append('self,')  # First line after def

i = 1
inside_method = True
while i < len(lines) and inside_method:
    line = lines[i]
    
    # Check if we've left the nested function
    # A new method at class level (4 spaces + def) or class definition
    if line.strip() and not line.startswith(' ' * 8):
        # We've reached something outside the nested function
        if line.lstrip().startswith('def ') or line.lstrip().startswith('class '):
            inside_method = False
            break
    
    # Dedent lines from 12 spaces to 8 spaces
    if line.startswith(' ' * 12):
        fixed_lines.append(line[4:])  # Remove 4 spaces
    elif line.startswith(' ' * 8):
        # Already at method-body level after dedent, keep as is
        fixed_lines.append(line[4:])  # Remove 4 spaces to get to new baseline
    elif line.strip() == '':
        fixed_lines.append(line)  # Keep empty lines
    else:
        # Lines with less indentation - might be end of method
        if line.lstrip().startswith('def ') and not line.startswith(' ' * 8):
            inside_method = False
            break
        fixed_lines.append(line)
    
    i += 1

# Reconstruct the file
new_content = before + '    def aggregate_decisions_two_phase(\n        ' + '\n'.join(fixed_lines)

# Add back the rest of the file
remaining_lines = lines[i:]
new_content += '\n'.join(remaining_lines)

with open(filepath, 'w') as f:
    f.write(new_content)

print(f"Successfully extracted and dedented aggregate_decisions_two_phase")
print(f"Processed {len(fixed_lines)} lines in method body")
