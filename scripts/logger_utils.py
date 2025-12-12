"""
Utility to check if the most recent folder in Modal storage contains Python files.

This script connects to the Modal volume 'robogen-generated_task_outputs' and checks
if the most recent folder contains any Python files.
"""

import modal
import os
from datetime import datetime
from pathlib import Path

app = modal.App("logger-utils")

# Reference the same volume as the main app
outputs_volume = modal.Volume.from_name("robogen-generated_task_outputs", create_if_missing=True)


@app.function(
    volumes={"/outputs": outputs_volume},
    timeout=300,
)
def check_most_recent_folder_for_python_files():
    """
    Check if the most recent folder in the outputs volume contains Python files.

    Returns:
        dict: Contains information about the most recent folder and whether it has Python files
    """
    outputs_path = Path("/outputs")

    # Check if the outputs directory exists
    if not outputs_path.exists():
        return {
            "status": "error",
            "message": "Outputs directory does not exist",
            "has_python_files": False
        }

    # Get all directories in the outputs folder
    directories = [d for d in outputs_path.iterdir() if d.is_dir()]

    if not directories:
        return {
            "status": "error",
            "message": "No folders found in outputs directory",
            "has_python_files": False
        }

    # Find the most recent directory by modification time
    most_recent_dir = max(directories, key=lambda d: d.stat().st_mtime)

    # Get all Python files in the most recent directory (including subdirectories)
    python_files = list(most_recent_dir.rglob("*.py"))

    # Get modification time of the most recent directory
    mod_time = datetime.fromtimestamp(most_recent_dir.stat().st_mtime)

    result = {
        "status": "success",
        "folder_name": most_recent_dir.name,
        "folder_path": str(most_recent_dir),
        "modified_time": mod_time.isoformat(),
        "has_python_files": len(python_files) > 0,
        "python_file_count": len(python_files),
        "python_files": [str(pf.relative_to(outputs_path)) for pf in python_files]
    }

    # Print summary
    print("=" * 80)
    print("MOST RECENT FOLDER CHECK")
    print("=" * 80)
    print(f"Folder: {result['folder_name']}")
    print(f"Path: {result['folder_path']}")
    print(f"Modified: {result['modified_time']}")
    print(f"Has Python files: {result['has_python_files']}")
    print(f"Python file count: {result['python_file_count']}")

    if python_files:
        print("\nPython files found:")
        for pf in result['python_files']:
            print(f"  - {pf}")
    else:
        print("\nNo Python files found in this folder.")

    print("=" * 80)

    return result


@app.function(
    volumes={"/outputs": outputs_volume},
    timeout=300,
)
def list_all_folders():
    """
    List all folders in the outputs volume with their modification times.

    Returns:
        dict: Contains list of all folders with metadata
    """
    outputs_path = Path("/outputs")

    if not outputs_path.exists():
        return {
            "status": "error",
            "message": "Outputs directory does not exist",
            "folders": []
        }

    # Get all directories with their metadata
    directories = []
    for d in outputs_path.iterdir():
        if d.is_dir():
            mod_time = datetime.fromtimestamp(d.stat().st_mtime)
            python_files = list(d.rglob("*.py"))

            directories.append({
                "name": d.name,
                "path": str(d),
                "modified_time": mod_time.isoformat(),
                "has_python_files": len(python_files) > 0,
                "python_file_count": len(python_files)
            })

    # Sort by modification time (most recent first)
    directories.sort(key=lambda x: x['modified_time'], reverse=True)

    print("=" * 80)
    print("ALL FOLDERS IN OUTPUTS VOLUME")
    print("=" * 80)
    print(f"Total folders: {len(directories)}\n")

    for i, folder in enumerate(directories, 1):
        print(f"{i}. {folder['name']}")
        print(f"   Modified: {folder['modified_time']}")
        print(f"   Python files: {folder['python_file_count']}")
        print(f"   Has .py files: {folder['has_python_files']}")
        print()

    print("=" * 80)

    return {
        "status": "success",
        "total_folders": len(directories),
        "folders": directories
    }


@app.local_entrypoint()
def main():
    """
    Main entry point for the script. Runs both checks.
    """
    print("\n🔍 Checking most recent folder for Python files...\n")
    recent_result = check_most_recent_folder_for_python_files.remote()

    print("\n📁 Listing all folders...\n")
    all_folders_result = list_all_folders.remote()

    return {
        "most_recent": recent_result,
        "all_folders": all_folders_result
    }


if __name__ == "__main__":
    # When run directly with Modal
    app.run()
