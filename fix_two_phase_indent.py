#!/usr/bin/env python3
"""
Quick script to fix the indentation of the two-phase method in ensemble_manager.py
"""

with open('finance_feedback_engine/decision_engine/ensemble_manager.py', 'r') as f:
    lines = f.readlines()

# Find the start of aggregate_decisions_two_phase method
start_idx = None
for i, line in enumerate(lines):
    if 'def aggregate_decisions_two_phase(' in line:
        start_idx = i
        break

if start_idx is None:
    print("Could not find aggregate_decisions_two_phase method")
    exit(1)

# Process lines after the method signature
# The method body should have 8-space indentation (2 levels)
# Currently it has 12-space indentation (3 levels)
fixed_lines = lines[:start_idx+1]  # Keep everything before and including the method signature

# Find the end of the method (next method definition or class end)
end_idx = None
for i in range(start_idx + 1, len(lines)):
    # Look for next method at same or higher level
    if lines[i].strip() and not lines[i].startswith(' ' * 12) and lines[i].startswith(' '):
        if lines[i].lstrip().startswith('def '):
            end_idx = i
            break
    # Or end of class
    if lines[i].strip().startswith('class ') or (lines[i].strip() and not lines[i].startswith(' ')):
        end_idx = i
        break

if end_idx is None:
    end_idx = len(lines)

print(f"Processing lines {start_idx+1} to {end_idx-1}")

# Dedent the method body by 4 spaces
for i in range(start_idx + 1, end_idx):
    line = lines[i]
    if line.startswith(' ' * 12):  # Has 3-level indentation
        # Reduce to 2-level (8 spaces)
        fixed_lines.append('    ' + line[12:])
    elif line.startswith(' ' * 8):  # Already at 2-level
        fixed_lines.append(line)
    elif line.strip() == '':  # Empty line
        fixed_lines.append(line)
    else:
        # Line doesn't match expected indentation, keep as-is
        fixed_lines.append(line)

# Add remaining lines
fixed_lines.extend(lines[end_idx:])

# Write back
with open('finance_feedback_engine/decision_engine/ensemble_manager.py', 'w') as f:
    f.writelines(fixed_lines)

print(f"Fixed indentation for aggregate_decisions_two_phase method")
print(f"Processed {end_idx - start_idx - 1} lines")
