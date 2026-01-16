#!/usr/bin/env python3
"""
Script to batch process tasks from a JSON file using Modal
Runs task generation only (no execution) for each task in the file
"""

import json
import subprocess
import sys
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Global lock for directory changes to prevent race conditions in multithreading
dir_lock = threading.Lock()


def run_task_generation(
    task_description: str, target_object: str, target_model_provider: str = "openrouter"
):
    """
    Run task generation for a single task using Modal

    Args:
        task_description: The task prompt/description
        target_object: The object to use for the task
        target_model_provider: Model provider to use (default: openrouter)

    Returns:
        bool: True if successful, False otherwise
    """
    # Get script directory - we'll use cwd to run modal from this directory
    script_dir = Path(__file__).parent.resolve()

    cmd = [
        "modal",
        "run",
        "./robogen_modal_conda_with_apis.py",  # Use relative path with ./
        "--target-model-provider",
        target_model_provider,
        "--task-description",
        task_description,
        "--target-object",
        target_object,
        "--generate-task",  # Only generate, don't execute
    ]

    print(f"\n{'=' * 80}")
    print(f"Running task: {task_description}")
    print(f"Object: {target_object}")
    print(f"Model Provider: {target_model_provider}")
    print(f"Script dir: {script_dir}")
    print(f"{'=' * 80}")
    print(f"Command: {' '.join(cmd)}\n")

    try:
        import os

        # Use relative path with cwd set - this is thread-safe
        print(f"DEBUG: Working directory: {script_dir}")
        print(f"DEBUG: Script file: ./robogen_modal_conda_with_apis.py")

        result = subprocess.run(
            cmd,
            capture_output=True,  # Capture output for error handling
            text=True,
            check=False,
            cwd=str(script_dir),  # Set working directory for this subprocess only
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        # Print output (only show errors or last few lines to avoid clutter in multithreaded mode)
        if result.returncode != 0:
            print(f"\n{'!' * 80}")
            print(f"ERROR for task: {task_description}")
            print(f"Return code: {result.returncode}")
            print(f"{'!' * 80}")
            if result.stdout:
                # Show last 30 lines of stdout for errors
                stdout_lines = result.stdout.strip().split("\n")
                print("Last lines of output:")
                print("\n".join(stdout_lines[-30:]))
            if result.stderr:
                print("\nStderr:")
                print(result.stderr)
            print(f"{'!' * 80}\n")
            return False
        else:
            # Success - only show minimal output
            return True

    except Exception as e:
        print(f"\n✗ Error running task: {e}")
        return False


def process_single_task(task_info):
    """
    Process a single task (wrapper for multithreading)

    Args:
        task_info: Tuple of (task_index, task_dict)

    Returns:
        Tuple of (task_index, prompt, success)
    """
    i, task = task_info
    prompt = task.get("prompt", "")
    obj = task.get("object", "Box")

    if not prompt:
        return (i, prompt, False)

    success = run_task_generation(
        task_description=prompt, target_object=obj, target_model_provider="openrouter"
    )

    return (i, prompt, success)


def main():
    """Main function to process all tasks from the JSON file"""

    # Path to the JSON file
    json_file = (
        Path(__file__).parent / "data" / "tasks" / "2026-01-02-from-GPT-5-2.json"
    )

    if not json_file.exists():
        print(f"Error: JSON file not found at {json_file}")
        sys.exit(1)

    # Load tasks from JSON
    print(f"Loading tasks from {json_file}")
    with open(json_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    print(f"Loaded {len(tasks)} tasks")
    print(f"Using 5 parallel workers for processing\n")

    # Track results
    successful_tasks = []
    failed_tasks = []

    # Process tasks with multithreading
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(process_single_task, (i, task)): (i, task)
            for i, task in enumerate(tasks, 1)
        }

        # Process completed tasks with tqdm progress bar
        with tqdm(total=len(tasks), desc="Processing tasks", unit="task") as pbar:
            for future in as_completed(future_to_task):
                task_index, prompt, success = future.result()

                if success:
                    successful_tasks.append((task_index, prompt))
                    pbar.set_postfix_str(f"[OK] {prompt[:50]}...")
                else:
                    failed_tasks.append((task_index, prompt))
                    pbar.set_postfix_str(f"[FAIL] {prompt[:50]}...")

                pbar.update(1)

    # Print summary
    print(f"\n{'=' * 80}")
    print("BATCH PROCESSING SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total tasks: {len(tasks)}")
    print(f"Successful: {len(successful_tasks)}")
    print(f"Failed: {len(failed_tasks)}")

    if failed_tasks:
        print(f"\nFailed tasks:")
        for task_num, prompt in failed_tasks:
            print(f"  {task_num}. {prompt}")

    print(f"{'=' * 80}\n")

    # Exit with appropriate code
    sys.exit(0 if len(failed_tasks) == 0 else 1)


if __name__ == "__main__":
    main()
