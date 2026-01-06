"""
Script to analyze robogen-generated_task_outputs from Modal volume.
Generates statistics and creates all_substeps.json file.
"""

import modal
import json
from pathlib import Path
from tqdm import tqdm
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from collections import defaultdict
from datetime import datetime
import re
from typing import Optional

app = modal.App("get-stats")

# Reference to the existing volume
volume = modal.Volume.from_name("robogen-generated_task_outputs", create_if_missing=False)

VOLUME_PATH = "/data"

image = modal.Image.debian_slim(python_version="3.9").pip_install("tqdm").pip_install("networkx").pip_install("matplotlib").pip_install("pyyaml")


def parse_timestamp_from_dirname(dirname: str) -> Optional[datetime]:
    """
    Extract timestamp from dirname.
    Expects format: <task_name>_YYYY-MM-DD-HH-MM-SS

    Returns:
        datetime object if timestamp found, None otherwise
    """
    # Pattern to match timestamp at the end: YYYY-MM-DD-HH-MM-SS
    pattern = r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})$'
    match = re.search(pattern, dirname)

    if match:
        try:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            return None
    return None


def extract_task_name(dirname: str) -> str:
    """
    Extract task name from dirname by removing timestamp.

    Returns:
        Task name without timestamp
    """
    # Remove timestamp pattern from the end
    pattern = r'_\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$'
    return re.sub(pattern, '', dirname)


def get_model_name_from_metadata(subdir_path: Path) -> Optional[str]:
    """
    Read model_name from prompt_metadata.yaml in the subdirectory.

    Args:
        subdir_path: Path to the subdirectory

    Returns:
        model_name if found, None otherwise
    """
    import yaml

    metadata_file = subdir_path / "prompt_metadata.yaml"
    if not metadata_file.exists():
        return None

    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)
            return metadata.get('model_name')
    except Exception:
        return None


@app.function(volumes={VOLUME_PATH: volume},image=image)
def analyze_task_outputs(unique_tasks: bool = False, after_date: Optional[str] = None, model_names: Optional[str] = None):
    """
    Analyze the task outputs directory and generate statistics.

    Args:
        unique_tasks: If True, only include one entry per unique task name (deduplicates by task name)
        after_date: If provided, only include tasks after this date (format: YYYY-MM-DD)
        model_names: Comma-separated list of model names to filter by (e.g., "glm-4.6,gpt-4.1")
    """
    from pathlib import Path
    from tqdm import tqdm
    import json

    base_path = Path(VOLUME_PATH)

    # Parse the after_date filter if provided
    cutoff_date = None
    if after_date:
        try:
            cutoff_date = datetime.strptime(after_date, "%Y-%m-%d")
            print(f"\nFiltering for tasks after: {after_date}")
        except ValueError:
            print(f"Warning: Invalid date format '{after_date}', expected YYYY-MM-DD. Ignoring filter.")

    # Parse the model_names filter if provided
    allowed_models = None
    if model_names:
        allowed_models = set(name.strip() for name in model_names.split(','))
        print(f"\nFiltering for model names: {', '.join(allowed_models)}")

    # Find all subdirectories using wildcard
    subdirs = [d for d in base_path.iterdir() if d.is_dir()]

    total_subdirs = len(subdirs)
    print(f"\nTotal subdirectories: {total_subdirs}")

    if total_subdirs == 0:
        print("No subdirectories found!")
        return

    # Initialize counters
    dirs_with_python = 0
    dirs_with_gif = 0
    all_substeps_data = []
    seen_task_names = {}  # For unique task filtering - maps task_name to (index, has_python)
    filtered_by_date = 0
    filtered_by_model = 0

    # Iterate through subdirectories with tqdm
    for subdir in tqdm(subdirs, desc="Processing directories"):
        dirname = subdir.name

        # Apply date filter if specified
        if cutoff_date:
            task_date = parse_timestamp_from_dirname(dirname)
            if task_date and task_date <= cutoff_date:
                filtered_by_date += 1
                continue

        # Apply model name filter if specified
        if allowed_models:
            model_name = get_model_name_from_metadata(subdir)
            if model_name not in allowed_models:
                filtered_by_model += 1
                continue

        # Check for Python files
        python_files = list(subdir.glob("**/*.py"))
        has_python = len(python_files) > 0
        if has_python:
            dirs_with_python += 1

        # Check for GIF files
        gif_files = list(subdir.glob("**/*.gif"))
        if gif_files:
            dirs_with_gif += 1

        # Read substeps.txt from <dirname>/task*/substeps.txt
        substeps_files = list(subdir.glob("task*/substeps.txt"))
        substeps = []
        if substeps_files:
            # Use the first match
            substeps_file = substeps_files[0]
            try:
                with open(substeps_file, 'r', encoding='utf-8') as f:
                    # Read lines and strip whitespace, filter out empty lines
                    substeps = [line.strip() for line in f.readlines() if line.strip()]
            except Exception as e:
                print(f"Warning: Could not read {substeps_file}: {e}")

        # Apply unique task filter with prioritization for subdirs with Python files
        if unique_tasks:
            task_name = extract_task_name(dirname)
            if task_name in seen_task_names:
                # Check if current has Python files and previous doesn't
                prev_index, prev_has_python = seen_task_names[task_name]

                # Replace previous entry if current has Python and previous doesn't
                if has_python and not prev_has_python:
                    all_substeps_data[prev_index] = {
                        "dirname": dirname,
                        "substeps": substeps
                    }
                    seen_task_names[task_name] = (prev_index, True)
                # Skip current entry (keep previous)
                continue
            else:
                # First time seeing this task name
                seen_task_names[task_name] = (len(all_substeps_data), has_python)
                all_substeps_data.append({
                    "dirname": dirname,
                    "substeps": substeps
                })
        else:
            # No unique filter, add all entries
            all_substeps_data.append({
                "dirname": dirname,
                "substeps": substeps
            })

    # Calculate percentages
    pct_with_python = (dirs_with_python / total_subdirs * 100) if total_subdirs > 0 else 0
    pct_with_gif = (dirs_with_gif / total_subdirs * 100) if total_subdirs > 0 else 0

    # Print statistics
    print(f"\nStatistics:")
    if cutoff_date:
        print(f"  - Filtered out (before {after_date}): {filtered_by_date}")
    if allowed_models:
        print(f"  - Filtered out (model not in {', '.join(allowed_models)}): {filtered_by_model}")
    if unique_tasks:
        print(f"  - Unique task names included: {len(seen_task_names)}")
    print(f"  - Directories with Python code: {dirs_with_python}/{total_subdirs} ({pct_with_python:.1f}%)")
    print(f"  - Directories with at least one GIF: {dirs_with_gif}/{total_subdirs} ({pct_with_gif:.1f}%)")

    # Create the JSON output
    output_data = {"data": all_substeps_data}

    # Write to all_substeps.json
    output_file = Path(VOLUME_PATH) / "all_substeps.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nCreated {output_file} with {len(all_substeps_data)} entries")

    # Commit changes to volume
    volume.commit()

    return output_data


def generate_substep_graph(all_substeps_data, output_filename="substeps_graph.png"):
    """
    Generate a directed graph showing substep transitions with frequency-based color coding.

    Args:
        all_substeps_data: List of dicts with 'dirname' and 'substeps' keys
        output_filename: Name of the output image file
    """
    import textwrap

    # Track transitions and their frequencies
    transition_counts = defaultdict(int)

    # Process all substep sequences
    for entry in all_substeps_data:
        substeps = entry.get("substeps", [])
        # Create transitions between consecutive substeps
        for i in range(len(substeps) - 1):
            current_step = substeps[i]
            next_step = substeps[i + 1]
            transition_counts[(current_step, next_step)] += 1

    if not transition_counts:
        print("\nWarning: No transitions found to visualize")
        return

    # Create directed graph
    G = nx.DiGraph()

    # Add edges with their frequencies
    for (source, target), count in transition_counts.items():
        G.add_edge(source, target, weight=count)

    # Get frequency range for color mapping
    frequencies = list(transition_counts.values())
    min_freq = min(frequencies)
    max_freq = max(frequencies)

    # Create figure with larger size for better visibility
    plt.figure(figsize=(24, 18))

    # Use spring layout with optimal parameters for force-directed graph
    # Higher k value = more space between nodes
    # More iterations = better convergence to optimal layout
    pos = nx.spring_layout(G, k=5.0, iterations=200, seed=42)

    # Calculate node size based on wrapped text dimensions
    # Wrapped at 15 chars, estimate needed diameter for circular node
    # Each line needs ~100 units, with padding
    max_lines = max(len(textwrap.wrap(str(node), width=15)) for node in G.nodes())
    # More conservative sizing: ~600 base + 400 per line of wrapped text
    node_size = 300 + (max_lines * 150)

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_color='lightblue',
                          node_size=node_size, alpha=0.9,
                          edgecolors='black', linewidths=2)

    # Wrap long labels to fit in nodes
    wrapped_labels = {}
    for node in G.nodes():
        label = str(node)
        # Wrap text at 15 characters per line to fit in nodes
        wrapped_label = '\n'.join(textwrap.wrap(label, width=15))
        wrapped_labels[node] = wrapped_label

    # Draw node labels with wrapped text
    nx.draw_networkx_labels(G, pos, labels=wrapped_labels,
                          font_size=7, font_weight='bold')

    # Create color map (light to dark blue based on frequency)
    cmap = plt.cm.YlOrRd  # Yellow to Orange to Red colormap
    norm = mcolors.Normalize(vmin=min_freq, vmax=max_freq)

    # Draw edges with color based on frequency
    for (source, target), count in transition_counts.items():
        color = cmap(norm(count))
        nx.draw_networkx_edges(G, pos, [(source, target)],
                              edge_color=[color], width=2,
                              arrowsize=20, arrowstyle='->',
                              connectionstyle='arc3,rad=0.1')

    # Create colorbar legend
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=plt.gca(), orientation='vertical',
                        fraction=0.046, pad=0.04)
    cbar.set_label('Transition Frequency', rotation=270, labelpad=25, fontsize=12)

    plt.title('Substep Transition Graph\n(Color indicates frequency: light = rare, dark = common)',
              fontsize=16, fontweight='bold', pad=20)
    plt.axis('off')
    plt.tight_layout()

    # Save the graph
    output_path = Path(output_filename)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"\nGraph saved to {output_path}")
    print(f"   - Total unique substeps (nodes): {G.number_of_nodes()}")
    print(f"   - Total transitions (edges): {G.number_of_edges()}")
    print(f"   - Frequency range: {min_freq} to {max_freq}")

    plt.close()


@app.local_entrypoint()
def main(unique_tasks: bool = False, after_date: Optional[str] = None, model_names: Optional[str] = None):
    """
    Main entry point for the script.

    Args:
        unique_tasks: Only include one entry per unique task name (ignores timestamp)
        after_date: Only include tasks after this date (format: YYYY-MM-DD)
        model_names: Comma-separated list of model names to filter by (e.g., "glm-4.6,gpt-4.1")
    """
    print("\nStarting analysis with filters:")
    print(f"  - Unique tasks only: {unique_tasks}")
    print(f"  - After date: {after_date or 'None (all dates)'}")
    print(f"  - Model names: {model_names or 'None (all models)'}")

    result = analyze_task_outputs.remote(unique_tasks=unique_tasks, after_date=after_date, model_names=model_names)

    # Save locally as well
    local_output = Path("all_substeps.json")
    with open(local_output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nAlso saved locally to {local_output}")

    # Generate the substep transition graph
    print("\nGenerating substep transition graph...")
    generate_substep_graph(result["data"], "substeps_graph.png")


if __name__ == "__main__":
    main()
