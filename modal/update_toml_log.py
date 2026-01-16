#!/usr/bin/env python3
"""
Utility script to update the CSV log with .toml file information
Scans the Modal volume and updates rows that are missing toml_files data
"""

import argparse
import csv
import subprocess
import os
from pathlib import Path


def get_toml_files_from_volume(output_directory):
    """
    List .toml files in the Modal volume for a given output directory

    Args:
        output_directory: The output directory name (e.g., "Task_Name_Box_12345_2025-12-11-10-30-00")

    Returns:
        List of .toml file paths, or empty list if error
    """
    if not output_directory:
        return []

    try:
        # Use modal volume ls to list files in the output directory
        cmd = f'export PYTHONIOENCODING="utf-8"; uv run modal volume ls robogen-generated_task_outputs {output_directory}'

        print(f"  Checking: {output_directory}")
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            # Parse the output to find .toml files
            toml_files = []
            for line in result.stdout.split("\n"):
                if line.strip().endswith(".toml"):
                    # Extract just the filename
                    filename = line.strip().split()[-1]
                    toml_files.append(filename)
            return toml_files
        else:
            print(f"    Warning: Could not list volume contents: {result.stderr}")
            return []
    except Exception as e:
        print(f"    Warning: Error listing volume: {e}")
        return []


def list_all_volume_directories():
    """
    List all directories in the Modal volume

    Returns:
        List of directory names
    """
    try:
        cmd = 'export PYTHONIOENCODING="utf-8"; uv run modal volume ls robogen-generated_task_outputs'

        print("Listing all directories in Modal volume...")
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=60
        )

        if result.returncode == 0:
            # Parse the output to find directories
            directories = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line and not line.endswith(".toml"):
                    # This is likely a directory
                    # Extract the name (last part if there are spaces)
                    dir_name = line.split()[-1].rstrip("/")
                    if dir_name:
                        directories.append(dir_name)
            return directories
        else:
            print(f"Error listing volume: {result.stderr}")
            return []
    except Exception as e:
        print(f"Error listing volume: {e}")
        return []


def update_csv_with_toml_files(csv_path, dry_run=False):
    """
    Update CSV rows with missing toml_files information

    Args:
        csv_path: Path to the CSV log file
        dry_run: If True, don't actually modify the CSV, just show what would be updated
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}")
        return

    # Read all rows from CSV
    rows = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    print(f"Read {len(rows)} rows from {csv_path}")

    # Find rows that need updating
    rows_to_update = []
    for i, row in enumerate(rows):
        if row.get("output_directory") and not row.get("toml_files"):
            rows_to_update.append((i, row))

    print(f"Found {len(rows_to_update)} rows with missing toml_files")

    if not rows_to_update:
        print("Nothing to update!")
        return

    # Update rows with toml file information
    updated_count = 0
    for idx, row in rows_to_update:
        output_dir = row["output_directory"]
        toml_files = get_toml_files_from_volume(output_dir)

        if toml_files:
            toml_str = ", ".join(toml_files)
            if dry_run:
                print(f"  [DRY RUN] Would update row {idx + 1}:")
                print(f"    Directory: {output_dir}")
                print(f"    TOML files: {toml_str}")
            else:
                rows[idx]["toml_files"] = toml_str
                updated_count += 1
                print(f"  ✓ Updated row {idx + 1}: {output_dir}")
                print(f"    TOML files: {toml_str}")
        else:
            print(f"  ✗ No TOML files found for: {output_dir}")

    # Write back to CSV if not dry run
    if not dry_run and updated_count > 0:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n✓ Updated {updated_count} rows in {csv_path}")
    elif dry_run:
        print(
            f"\n[DRY RUN] Would update {len([r for r in rows_to_update if get_toml_files_from_volume(r[1]['output_directory'])])} rows"
        )


def scan_volume_and_match(csv_path):
    """
    Alternative approach: Scan the entire Modal volume and try to match directories
    to tasks in the CSV
    """
    print("Scanning Modal volume for all directories...")
    directories = list_all_volume_directories()

    if not directories:
        print("No directories found in volume")
        return

    print(f"\nFound {len(directories)} directories in volume:")
    for dir_name in directories[:10]:  # Show first 10
        print(f"  - {dir_name}")
    if len(directories) > 10:
        print(f"  ... and {len(directories) - 10} more")

    # Get toml files for each directory
    print("\nScanning for .toml files...")
    dir_toml_map = {}
    for dir_name in directories:
        toml_files = get_toml_files_from_volume(dir_name)
        if toml_files:
            dir_toml_map[dir_name] = toml_files
            print(f"  {dir_name}: {len(toml_files)} TOML files")

    print(f"\n✓ Found {len(dir_toml_map)} directories with TOML files")

    # Show summary
    if dir_toml_map:
        print("\nSummary of TOML files by directory:")
        for dir_name, toml_files in sorted(dir_toml_map.items()):
            print(f"\n{dir_name}:")
            for toml_file in toml_files:
                print(f"  - {toml_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Update CSV log with .toml file information from Modal volume"
    )
    parser.add_argument(
        "--csv-log", type=str, default="task_runs_log.csv", help="Path to CSV log file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without modifying the CSV",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Just scan the Modal volume and show all directories with TOML files",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("TOML FILE LOG UPDATER")
    print("=" * 80)

    if args.scan_only:
        scan_volume_and_match(args.csv_log)
    else:
        update_csv_with_toml_files(args.csv_log, dry_run=args.dry_run)

    print("=" * 80)
    print("✓ DONE")
    print("=" * 80)


if __name__ == "__main__":
    main()
