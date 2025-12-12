import modal
import os
from pathlib import Path

# Create Modal app
app = modal.App("robogen-task-visualizer")

# Access the existing outputs volume
outputs_volume = modal.Volume.from_name("robogen-generated_task_outputs", create_if_missing=False)

# Define image with visualization libraries
image = (
    modal.Image.debian_slim()
    .pip_install(
        "networkx",
        "matplotlib",
        "Pillow"
    )
)

@app.function(
    image=image,
    volumes={"/outputs": outputs_volume},
    timeout=3600,
)
def visualize_tasks():
    """
    Explore all task directories in the outputs volume and create graph visualizations
    showing the directory structure with task name as root and Python files as nodes.
    """
    import networkx as nx
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend

    outputs_dir = Path("/outputs")

    # Check if outputs directory exists and has content
    if not outputs_dir.exists():
        print("⚠ Warning: /outputs directory does not exist")
        return {"status": "error", "message": "Outputs directory not found"}

    # List all task directories
    task_dirs = [d for d in outputs_dir.iterdir() if d.is_dir()]

    if not task_dirs:
        print("⚠ Warning: No task directories found in /outputs")
        return {"status": "error", "message": "No task directories found"}

    print(f"Found {len(task_dirs)} task directories")
    print("=" * 80)

    all_graphs = []

    for task_dir in sorted(task_dirs):
        task_name = task_dir.name
        print(f"\nProcessing task: {task_name}")
        print("-" * 80)

        # Find all Python files recursively
        python_files = []
        for root, dirs, files in os.walk(task_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(task_dir)
                    python_files.append(str(rel_path))

        print(f"  Found {len(python_files)} Python file(s)")

        # Create graph
        G = nx.Graph()

        # Add root node (task name)
        G.add_node(task_name, node_type='root')

        # Add Python file nodes and edges
        for py_file in python_files:
            G.add_node(py_file, node_type='file')
            G.add_edge(task_name, py_file)
            print(f"    - {py_file}")

        # Create visualization
        plt.figure(figsize=(14, 10))

        # Use hierarchical layout
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

        # Draw nodes with different colors
        node_colors = []
        node_sizes = []
        for node in G.nodes():
            if G.nodes[node]['node_type'] == 'root':
                node_colors.append('#FF6B6B')  # Red for task name
                node_sizes.append(3000)
            else:
                node_colors.append('#4ECDC4')  # Teal for files
                node_sizes.append(2000)

        # Draw the graph
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.9)
        nx.draw_networkx_edges(G, pos, width=2, alpha=0.5, edge_color='#95A5A6')

        # Draw labels with better formatting
        labels = {}
        for node in G.nodes():
            if G.nodes[node]['node_type'] == 'root':
                # Wrap long task names
                if len(node) > 40:
                    words = node.split('_')
                    lines = []
                    current_line = []
                    current_length = 0
                    for word in words:
                        if current_length + len(word) + 1 <= 40:
                            current_line.append(word)
                            current_length += len(word) + 1
                        else:
                            lines.append('_'.join(current_line))
                            current_line = [word]
                            current_length = len(word)
                    if current_line:
                        lines.append('_'.join(current_line))
                    labels[node] = '\n'.join(lines)
                else:
                    labels[node] = node
            else:
                # Show only filename for files, wrap if needed
                filename = Path(node).name
                if len(filename) > 30:
                    labels[node] = filename[:27] + '...'
                else:
                    labels[node] = filename

        nx.draw_networkx_labels(G, pos, labels, font_size=9, font_weight='bold')

        plt.title(f"Task Structure: {task_name}", fontsize=14, fontweight='bold', pad=20)
        plt.axis('off')
        plt.tight_layout()

        # Save the figure
        output_file = task_dir / f"{task_name}_graph.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"  ✓ Saved graph to: {output_file}")

        all_graphs.append({
            'task_name': task_name,
            'python_files': python_files,
            'graph_path': str(output_file)
        })

    # Commit volume changes to persist the generated graphs
    print("\n" + "=" * 80)
    print("⟳ Committing volume changes...")
    outputs_volume.commit()
    print("✓ All graphs saved to outputs volume!")
    print("=" * 80)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tasks visualized: {len(all_graphs)}")
    for graph_info in all_graphs:
        print(f"\n  Task: {graph_info['task_name']}")
        print(f"    Files: {len(graph_info['python_files'])}")
        print(f"    Graph: {graph_info['graph_path']}")

    return {
        "status": "success",
        "tasks_processed": len(all_graphs),
        "graphs": all_graphs
    }


@app.local_entrypoint()
def main():
    """
    Main entrypoint to run the task visualization
    """
    print("\n" + "=" * 80)
    print("ROBOGEN TASK VISUALIZER")
    print("=" * 80 + "\n")

    print("Connecting to Modal volume: robogen-generated_task_outputs")
    print("Generating graph visualizations for all tasks...")
    print()

    result = visualize_tasks.remote()

    if result["status"] == "success":
        print("\n" + "=" * 80)
        print("✓ VISUALIZATION COMPLETE!")
        print("=" * 80)
        print(f"\nProcessed {result['tasks_processed']} task(s)")
        print("\nGraph files have been saved to the Modal volume at:")
        print("  /outputs/<task_name>/<task_name>_graph.png")
    else:
        print("\n" + "=" * 80)
        print("✗ VISUALIZATION FAILED")
        print("=" * 80)
        print(f"\nError: {result.get('message', 'Unknown error')}")
