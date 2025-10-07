"""
Test file for code review agent.
This file contains various issues for testing purposes.
"""

import os
import sys

def add(a, b):
    # This function adds two numbers
    return a + b

# Security issue: Using exec with user input
user_input = input("Enter something: ")
exec(user_input)  # Dangerous: Executes arbitrary code

# Maintainability issue: Unused variable
unused = "This variable is not used"

# Style issue: Inconsistent quotes
print("Hello, World!")
print('Hello again!')

# Potential bug: Division by zero
def divide(a, b):
    return a / b  # No check for b == 0

# Bad practice: Catching too broad exception
try:
    result = 10 / 0
except:  # Should specify exception type
    print("An error occurred")

# Inefficient code: Using list when set would be better
duplicates = [1, 2, 2, 3, 4, 4, 5]
unique = list(set(duplicates))  # More efficient way to get unique values

# Bad variable naming
x = 10  # Non-descriptive variable name
y = 20
z = x + y
print(f"The result is {z}")

# Unused import
import json  # Imported but not used

# Too many arguments
def process_data(a, b, c, d, e, f):  # Too many arguments
    return a + b + c + d + e + f
