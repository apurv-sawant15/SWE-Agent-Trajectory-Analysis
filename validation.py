# This is a validation script to help you read a JSON file containing trajectory analysis results
# changed the filename variable to point to your JSON file
# You can run this script to see a formatted report of the analysis results.
# Make sure you don't missing any keys in the JSON file.

import json
import os
from pprint import pprint

# Define the filename 
filename = 'example.json' 


# --- Main Report Generation ---

def generate_report(data):
    """Prints the structured report based on the loaded JSON data."""
    
    print("\n" + "="*80)
    print(f"AUTOMATED TRAJECTORY ANALYSIS REPORT: {data['Traj ID']}".center(80))
    print("="*80 + "\n")

    # --- Section 1: Issue Overview ---
    print("## Issue Overview")
    print("-" * 25)
    print(f"**Trajectory ID:** {data['Traj ID']}")
    print(f"**Issue Summary:** {data['Issue Summary']}")
    
    
    # --- Section 2: Agent Localization & Search Analysis ---
    
    print("\n## 1. Reproduction Code")
    print(f"The agent used the following scripts to reproduce and verify the issue: {data['Reproduction Code']}")
    print(f"**Self-Correction/Debugging (1.1):** {data['1.1']}")
    print(f"**Debugging Scripts (1.2):** {data['1.2']}")
    
    print("\n## 2. Localization and Debugging")
    print("-" * 35)
    print(f"**Search Tool Used (2.1):** {data['2.1']}")
    if data['2.1'] == "NO":
        print(f"**Search Analysis (2.2):** {data['2.2']}")
    


    # --- Section 3: Code Modification (The Fix) ---
    print("\n## 3. Code Modification")
    print("-" * 25)
    print(f"**Patch Details:** {data['Edit the Code']}")


    # --- Section 4: Validation and Tool Use ---
    print("\n## 4. Validation & Metrics")
    print("-" * 25)
    print(f"**Reproduction Tests Passed (4.1):** {data['4.1']}")
    print(f"**Validation Summary (4.2):** {data['4.2']}")
    
    print("\n## 5. Tool Usage Statistics")
    # Use pprint for clean dictionary printing of tool use
    pprint(data['Tool-use analysis'])
    
    print("\n" + "="*80)


# --- Execution ---

try:
    # 1. Read the JSON data from the file
    with open(filename, 'r') as f:
        data = json.load(f)
    generate_report(data)

except FileNotFoundError:
    print(f"\nError: The file '{filename}' was not found. Please ensure the file exists and is in the correct path.")
except json.JSONDecodeError:
    print(f"\nError: The file '{filename}' contains invalid JSON format.")
except KeyError as e:
    print(f"\nError: Missing expected key in the JSON data: {e}")
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")