#!/usr/bin/env python3
"""
Clustering analysis of robotic task substeps using OpenAI embeddings and GPT summaries.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter

import numpy as np
from openai import OpenAI
from sklearn.cluster import KMeans
from tqdm import tqdm

from dotenv import load_dotenv

load_dotenv()


def load_substeps(filepath: str) -> tuple[List[str], Dict[str, Any]]:
    """Load and extract all unique substeps from the JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Collect all substeps
    all_substeps = []
    for entry in data["data"]:
        all_substeps.extend(entry["substeps"])

    # Get unique substeps while preserving order
    seen = set()
    unique_substeps = []
    for substep in all_substeps:
        if substep not in seen:
            seen.add(substep)
            unique_substeps.append(substep)

    print(f"Loaded {len(all_substeps)} total substeps ({len(unique_substeps)} unique)")
    return unique_substeps, data


def get_embeddings(
    client: OpenAI, texts: List[str], model: str = "text-embedding-3-small"
) -> np.ndarray:
    """Get embeddings for a list of texts using OpenAI API."""
    # OpenAI API has a limit, so batch if needed
    batch_size = 100
    all_embeddings = []

    for i in tqdm(range(0, len(texts), batch_size), desc="Getting embeddings"):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return np.array(all_embeddings)


def perform_clustering(
    embeddings: np.ndarray, k_values: List[int]
) -> Dict[int, np.ndarray]:
    """Perform k-means clustering for different k values."""
    results = {}

    for k in tqdm(k_values, desc="Performing k-means clustering"):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)
        results[k] = labels

    return results


def get_cluster_summary(
    client: OpenAI, substeps: List[str], model: str = "gpt-4o"
) -> str:
    """Use GPT to generate a single keyword that summarizes a cluster of substeps."""
    # Limit the number of examples to avoid token limits
    examples = substeps[:20] if len(substeps) > 20 else substeps

    prompt = f"""Given the following robotic task substeps, provide a SINGLE WORD (or short keyword/phrase of max 3 words) that best summarizes what these actions have in common:

{chr(10).join(f"- {step}" for step in examples)}

Respond with ONLY the keyword/phrase, nothing else."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes robot task actions into concise keywords.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=20,
    )

    return response.choices[0].message.content.strip()


def generate_cluster_names(
    client: OpenAI, substeps: List[str], clustering_results: Dict[int, np.ndarray]
) -> Dict[int, Dict[int, Dict[str, Any]]]:
    """Generate keyword summaries for each cluster using GPT."""
    all_summaries = {}

    for k, labels in tqdm(
        list(clustering_results.items()), desc="Generating cluster summaries"
    ):
        cluster_info = {}

        for cluster_id in tqdm(range(k), desc=f"k={k} clusters", leave=False):
            # Get substeps in this cluster
            cluster_mask = labels == cluster_id
            cluster_substeps = [
                substeps[i] for i in range(len(substeps)) if cluster_mask[i]
            ]

            # Get summary
            summary = get_cluster_summary(client, cluster_substeps)

            cluster_info[cluster_id] = {
                "summary": summary,
                "size": len(cluster_substeps),
                "examples": cluster_substeps[:5],  # Include first 5 as examples
            }

        all_summaries[k] = cluster_info

    return all_summaries


def export_results(
    substeps: List[str],
    original_data: Dict[str, Any],
    clustering_results: Dict[int, np.ndarray],
    cluster_summaries: Dict[int, Dict[int, Dict[str, Any]]],
    output_path: str,
):
    """Export clustering results to JSON, preserving original data structure."""
    # Create substep to cluster mapping for all k values
    substep_to_clusters = {}
    for i, substep in enumerate(substeps):
        substep_to_clusters[substep] = {
            f"k_{k}": int(labels[i]) for k, labels in clustering_results.items()
        }

    # Augment original data with clustering information
    augmented_data = []
    for entry in original_data["data"]:
        augmented_entry = {"dirname": entry["dirname"], "substeps": []}

        for substep in entry["substeps"]:
            if substep:  # Only process non-empty substeps
                substep_info = {
                    "text": substep,
                    "clusters": substep_to_clusters.get(substep, {}),
                }
                augmented_entry["substeps"].append(substep_info)

        augmented_data.append(augmented_entry)

    # Build comprehensive results structure
    results = {
        "metadata": {
            "total_unique_substeps": len(substeps),
            "total_entries": len(original_data["data"]),
            "k_values": list(clustering_results.keys()),
            "embedding_model": "text-embedding-3-small",
            "summary_model": "gpt-4o",
        },
        "data": augmented_data,
        "cluster_summaries": {
            f"k_{k}": {
                f"cluster_{cid}": {
                    "summary": info["summary"],
                    "size": info["size"],
                    "examples": info["examples"],
                }
                for cid, info in cluster_summaries[k].items()
            }
            for k in clustering_results.keys()
        },
    }

    # Save to file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults exported to {output_path}")


def main():
    """Main execution function."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Cluster robotic task substeps using OpenAI embeddings and GPT summaries."
    )
    parser.add_argument(
        "-f",
        "--file",
        type=str,
        default="all_substeps.json",
        help="Path to input JSON file (default: all_substeps.json)",
    )
    args = parser.parse_args()

    # Configuration
    input_file = Path(args.file)
    if not input_file.is_absolute():
        input_file = Path(__file__).parent / input_file

    output_file = input_file.parent / "clustering_results.json"
    k_values = list(range(2, 11))  # k = 2 to 10

    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)

    print("=" * 60)
    print("Robotic Task Substep Clustering Analysis")
    print("=" * 60)

    # Load substeps
    substeps, original_data = load_substeps(str(input_file))

    # Get embeddings
    embeddings = get_embeddings(client, substeps)

    # Perform clustering
    clustering_results = perform_clustering(embeddings, k_values)

    # Generate cluster summaries
    cluster_summaries = generate_cluster_names(client, substeps, clustering_results)

    # Export results
    export_results(
        substeps, original_data, clustering_results, cluster_summaries, str(output_file)
    )

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
