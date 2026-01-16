#!/usr/bin/env python3
"""
Batch task runner for RoboGen tasks
Loads tasks from a file and runs each task multiple times with different models
Logs results to a CSV file for tracking
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix encoding issues on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def load_tasks(task_file):
    """Load tasks from a text file, filtering out empty lines"""
    tasks = []
    with open(task_file, "r") as f:
        for line in f:
            # Remove the line number prefix (e.g., "     1→")
            # and strip whitespace
            task = line.strip()
            if "→" in task:
                task = task.split("→", 1)[1].strip()

            # Skip empty tasks
            if task:
                tasks.append(task)

    return tasks


def get_model_provider(model_name):
    """Map model names to provider names"""
    model_map = {
        "glm-4.6": "novita",
        "gpt-4": "openai",
    }
    return model_map.get(model_name, model_name)


def parse_output_directory(stdout_text):
    """
    Parse the output directory from modal stdout
    Looks for patterns like: data/generated_task_from_description/Task_Name_Box_ID_TIMESTAMP/
    """
    import re

    # Look for directory patterns in the output
    pattern = r"data/generated_task_from_description/([^\s\n]+)"
    matches = re.findall(pattern, stdout_text)
    if matches:
        # Return the first match (should be the output directory)
        return matches[0].rstrip("/")
    return None


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
        cmd = (
            f"uv run modal volume ls robogen-generated_task_outputs {output_directory}"
        )

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
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
            print(f"Warning: Could not list volume contents: {result.stderr}")
            return []
    except Exception as e:
        print(f"Warning: Error listing volume: {e}")
        return []


def run_task_generation(task_description, model_provider, detach=True):
    """
    Run a single task generation using modal

    Returns:
        dict with 'returncode', 'stdout', 'stderr', 'app_id', 'output_directory', 'toml_files'
    """
    # Construct the modal command
    cmd_parts = ["uv run modal run"]

    if detach:
        cmd_parts.append("--detach")

    cmd_parts.extend(
        [
            "robogen_modal_conda_with_apis.py",
            "--task-description",
            f'"{task_description}"',
            "--target-model-provider",
            model_provider,
            "--generate-task",
        ]
    )

    cmd = " ".join(cmd_parts)

    print(f"\nExecuting: {cmd}")

    # Run the command
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    # Try to extract app ID from output if detached
    app_id = None
    output_directory = None
    toml_files = []

    if result.returncode == 0:
        # Look for app ID if detached
        if detach:
            for line in result.stdout.split("\n"):
                if "modal.com" in line or "App ID" in line:
                    # Extract app ID if available
                    parts = line.split()
                    for part in parts:
                        if part.startswith("ap-"):
                            app_id = part
                            break

        # Parse output directory from stdout
        output_directory = parse_output_directory(result.stdout)

        # If not in detach mode and we found the output directory, try to get toml files
        if not detach and output_directory:
            toml_files = get_toml_files_from_volume(output_directory)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "app_id": app_id,
        "output_directory": output_directory,
        "toml_files": ", ".join(toml_files) if toml_files else "",
    }


def init_csv_log(csv_path):
    """Initialize CSV log file with headers if it doesn't exist"""
    file_exists = os.path.exists(csv_path)

    if not file_exists:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "task_description",
                    "model_name",
                    "model_provider",
                    "run_number",
                    "status",
                    "app_id",
                    "output_directory",
                    "toml_files",
                    "notes",
                ],
            )
            writer.writeheader()

    return csv_path


def log_task_run(
    csv_path,
    task_description,
    model_name,
    model_provider,
    run_number,
    status,
    app_id=None,
    output_directory=None,
    toml_files=None,
    notes=None,
):
    """Log a task run to the CSV file"""
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "task_description",
                "model_name",
                "model_provider",
                "run_number",
                "status",
                "app_id",
                "output_directory",
                "toml_files",
                "notes",
            ],
        )

        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(),
                "task_description": task_description,
                "model_name": model_name,
                "model_provider": model_provider,
                "run_number": run_number,
                "status": status,
                "app_id": app_id or "",
                "output_directory": output_directory or "",
                "toml_files": toml_files or "",
                "notes": notes or "",
            }
        )


def main():
    parser = argparse.ArgumentParser(
        description="Run RoboGen tasks in batch mode with multiple models"
    )
    parser.add_argument(
        "--task-file",
        type=str,
        default="data/tasks/2025-12-11.txt",
        help="Path to file containing tasks (one per line)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="glm-4.6",
        choices=["glm-4.6", "gpt-4"],
        help="Model to use for task generation",
    )
    parser.add_argument(
        "--runs-per-task", type=int, default=5, help="Number of times to run each task"
    )
    parser.add_argument(
        "--csv-log", type=str, default="task_runs_log.csv", help="Path to CSV log file"
    )
    parser.add_argument(
        "--delay", type=int, default=2, help="Delay in seconds between task submissions"
    )
    parser.add_argument(
        "--no-detach",
        action="store_true",
        help="Run tasks without --detach flag (wait for completion)",
    )
    parser.add_argument(
        "--start-from", type=int, default=0, help="Start from task number N (0-indexed)"
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Maximum number of tasks to run (useful for testing)",
    )

    args = parser.parse_args()

    # Load tasks
    print(f"Loading tasks from: {args.task_file}")
    tasks = load_tasks(args.task_file)
    print(f"Loaded {len(tasks)} tasks")

    # Apply start-from and max-tasks filters
    if args.start_from > 0:
        tasks = tasks[args.start_from :]
        print(f"Starting from task {args.start_from}")

    if args.max_tasks:
        tasks = tasks[: args.max_tasks]
        print(f"Limited to {args.max_tasks} tasks")

    # Initialize CSV log
    csv_path = init_csv_log(args.csv_log)
    print(f"Logging to: {csv_path}")

    # Get model provider
    model_provider = get_model_provider(args.model)
    print(f"Using model: {args.model} (provider: {model_provider})")
    print(f"Runs per task: {args.runs_per_task}")
    print(f"Detach mode: {not args.no_detach}")
    print()

    # Run tasks
    total_runs = len(tasks) * args.runs_per_task
    current_run = 0

    for task_idx, task in enumerate(tasks, start=args.start_from):
        print("=" * 80)
        print(f"Task {task_idx + 1}/{len(tasks) + args.start_from}: {task}")
        print("=" * 80)

        for run_num in range(1, args.runs_per_task + 1):
            current_run += 1
            print(
                f"\n[Run {run_num}/{args.runs_per_task}] (Overall: {current_run}/{total_runs})"
            )

            try:
                # Run the task
                result = run_task_generation(
                    task_description=task,
                    model_provider=model_provider,
                    detach=not args.no_detach,
                )

                # Determine status
                if result["returncode"] == 0:
                    status = "submitted" if not args.no_detach else "completed"
                    print(f"[OK] Task {status}")
                    if result.get("output_directory"):
                        print(f"  Output directory: {result['output_directory']}")
                    if result.get("toml_files"):
                        print(f"  TOML files: {result['toml_files']}")
                else:
                    status = "failed"
                    print(f"[FAIL] Task failed with return code {result['returncode']}")
                    print(f"Error: {result['stderr']}")

                # Log the run
                log_task_run(
                    csv_path=csv_path,
                    task_description=task,
                    model_name=args.model,
                    model_provider=model_provider,
                    run_number=run_num,
                    status=status,
                    app_id=result.get("app_id"),
                    output_directory=result.get("output_directory"),
                    toml_files=result.get("toml_files"),
                    notes=result["stderr"] if status == "failed" else None,
                )

                # Delay before next submission (except for last run)
                if current_run < total_runs:
                    print(f"Waiting {args.delay} seconds before next submission...")
                    time.sleep(args.delay)

            except Exception as e:
                print(f"[ERROR] Exception occurred: {e}")
                log_task_run(
                    csv_path=csv_path,
                    task_description=task,
                    model_name=args.model,
                    model_provider=model_provider,
                    run_number=run_num,
                    status="error",
                    notes=str(e),
                )

    print("\n" + "=" * 80)
    print("[OK] BATCH RUN COMPLETE!")
    print(f"Total tasks: {len(tasks)}")
    print(f"Total runs: {total_runs}")
    print(f"Log file: {csv_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
