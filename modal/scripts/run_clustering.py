#!/usr/bin/env python3
"""
Clustering analysis of robotic task substeps using OpenAI embeddings and GPT summaries.
Supports hierarchical k-means (default), HDBSCAN, standard k-means, and spectral clustering algorithms.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter

import numpy as np
from openai import OpenAI
from sklearn.cluster import KMeans, BisectingKMeans, DBSCAN, HDBSCAN, SpectralClustering
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
    embeddings: np.ndarray,
    k_values: List[int] = None,
    method: str = "hierarchical-kmeans",
    min_cluster_sizes: List[int] = None,
    min_samples: int = 2
) -> Dict[int, np.ndarray]:
    """Perform clustering for different parameter values.

    Args:
        embeddings: The embedding vectors
        k_values: List of k values for k-means, hierarchical k-means, and spectral clustering
        method: Clustering method ('hierarchical-kmeans', 'kmeans', 'spectral', or 'hdbscan')
        min_cluster_sizes: List of min_cluster_size values for HDBSCAN
        min_samples: Minimum samples for HDBSCAN

    Returns:
        Dictionary mapping parameter value to cluster labels
    """
    results = {}

    if method == "hierarchical-kmeans":
        for k in tqdm(k_values, desc="Performing hierarchical k-means clustering"):
            bisecting_kmeans = BisectingKMeans(
                n_clusters=k,
                random_state=42,
                n_init=10,
                bisecting_strategy='largest_cluster'
            )
            labels = bisecting_kmeans.fit_predict(embeddings)
            results[k] = labels
    elif method == "kmeans":
        for k in tqdm(k_values, desc="Performing k-means clustering"):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)
            results[k] = labels
    elif method == "spectral":
        for k in tqdm(k_values, desc="Performing spectral clustering"):
            spectral = SpectralClustering(
                n_clusters=k,
                random_state=42,
                affinity='rbf',
                assign_labels='kmeans'
            )
            labels = spectral.fit_predict(embeddings)
            results[k] = labels
    elif method == "hdbscan":
        for min_cluster_size in tqdm(min_cluster_sizes, desc="Performing HDBSCAN clustering"):
            clusterer = HDBSCAN(
                min_cluster_size=min_cluster_size,
                min_samples=min_samples,
                metric='euclidean',
                cluster_selection_method='eom'
            )
            labels = clusterer.fit_predict(embeddings)
            results[min_cluster_size] = labels
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise = list(labels).count(-1)
            print(f"  min_cluster_size={min_cluster_size}: {n_clusters} clusters, {n_noise} noise points")

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

        # Get unique cluster IDs (excluding -1 for noise in DBSCAN)
        unique_clusters = sorted(set(labels))

        for cluster_id in tqdm(unique_clusters, desc=f"k={k} clusters", leave=False):
            # Get substeps in this cluster
            cluster_mask = labels == cluster_id
            cluster_substeps = [
                substeps[i] for i in range(len(substeps)) if cluster_mask[i]
            ]

            # Get summary (or label as noise for DBSCAN noise points)
            if cluster_id == -1:
                summary = "Noise/Outliers"
            else:
                summary = get_cluster_summary(client, cluster_substeps)

            cluster_info[cluster_id] = {
                "summary": summary,
                "size": len(cluster_substeps),
                "examples": cluster_substeps[:5],  # Include first 5 as examples
            }

        all_summaries[k] = cluster_info

    return all_summaries


def gpt_prompted_categorization(
    client: OpenAI, substeps: List[str], k: int, model: str = "gpt-4o"
) -> Dict[str, str]:
    """Use GPT to directly map each substep to a category name (up to k categories)."""
    substeps_list = "\n".join(f"- {step}" for step in substeps)

    prompt = f"""You are tasked with categorizing robotic task substeps into up to {k} meaningful categories.

Here are all the substeps:

{substeps_list}

Please assign each substep to a category. Create meaningful category names (1-3 words each) and use up to {k} categories total.

Respond with a JSON object mapping each substep text to its category name:
{{
  "substep text 1": "category_name",
  "substep text 2": "category_name",
  ...
}}

Respond with ONLY the JSON object, no other text."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that categorizes robot task actions. You always respond with valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    # Parse and return the mapping
    substep_to_category = json.loads(response.choices[0].message.content)
    return substep_to_category


def transform_gpt_categorization_to_clustering_format(
    substeps: List[str], substep_to_category: Dict[str, str]
) -> tuple[np.ndarray, Dict[int, Dict[str, Any]]]:
    """Transform GPT categorization mapping into clustering format (labels + cluster_info)."""
    # Get unique category names and create category_name -> id mapping
    unique_categories = list(set(substep_to_category.values()))
    category_name_to_id = {name: idx for idx, name in enumerate(unique_categories)}

    # Create labels array
    labels = np.zeros(len(substeps), dtype=int)
    for i, substep in enumerate(substeps):
        category_name = substep_to_category.get(substep, unique_categories[0])
        labels[i] = category_name_to_id[category_name]

    # Create cluster_info in the same format as embedding-based clustering
    cluster_info = {}
    for cat_id, cat_name in enumerate(unique_categories):
        # Get all substeps in this category
        category_substeps = [
            substeps[i] for i in range(len(substeps))
            if substep_to_category.get(substeps[i]) == cat_name
        ]

        cluster_info[cat_id] = {
            "summary": cat_name,
            "size": len(category_substeps),
            "examples": category_substeps[:5],
        }

    return labels, cluster_info


def export_results(
    substeps: List[str],
    original_data: Dict[str, Any],
    clustering_results: Dict[int, np.ndarray],
    cluster_summaries: Dict[int, Dict[int, Dict[str, Any]]],
    output_path: str,
    method: str = "text-embedding-3-small",
    clustering_method: str = "hierarchical-kmeans",
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
            "method": method,
            "clustering_method": clustering_method,
            "embedding_model": "text-embedding-3-small" if method == "text-embedding-3-small" else None,
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
    parser.add_argument(
        "--embedding-type",
        type=str,
        choices=["text-embedding-3-small", "gpt-5.2-prompted", "all"],
        default="text-embedding-3-small",
        help="Type of embedding/categorization to use (default: text-embedding-3-small)",
    )
    parser.add_argument(
        "--drop-first-word",
        action="store_true",
        help="Remove the first word from each substep before generating embeddings",
    )
    parser.add_argument(
        "--clustering-method",
        type=str,
        choices=["hierarchical-kmeans", "kmeans", "spectral", "hdbscan"],
        default="hierarchical-kmeans",
        help="Clustering method to use (default: hierarchical-kmeans)",
    )
    parser.add_argument(
        "--min-k",
        type=int,
        default=2,
        help="Minimum number of clusters for k-means/hierarchical k-means (default: 2)",
    )
    parser.add_argument(
        "--max-k",
        type=int,
        default=9,
        help="Maximum number of clusters for k-means/hierarchical k-means (default: 9)",
    )
    parser.add_argument(
        "--min-cluster-sizes",
        type=str,
        default="2,5,10,15,20",
        help="Comma-separated min_cluster_size values for HDBSCAN (default: 2,5,10,15,20)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=2,
        help="Minimum samples for HDBSCAN (default: 2)",
    )
    args = parser.parse_args()

    # Configuration
    input_file = Path(args.file)
    if not input_file.is_absolute():
        input_file = Path(__file__).parent / input_file

    clustering_method = args.clustering_method

    # Parse parameters based on clustering method
    if clustering_method in ["kmeans", "hierarchical-kmeans", "spectral"]:
        k_values = list(range(args.min_k, args.max_k + 1))
        min_cluster_sizes = None
        param_suffix = f"_k{args.min_k}-{args.max_k}"
    else:  # hdbscan
        k_values = None
        min_cluster_sizes = [int(x) for x in args.min_cluster_sizes.split(",")]
        param_suffix = f"_mincluster{args.min_cluster_sizes.replace(',', '-')}_minsamples{args.min_samples}"

    output_file = input_file.parent / f"clustering_results_{clustering_method}{param_suffix}.json"

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

    embedding_type = args.embedding_type

    # Handle different embedding types
    if embedding_type == "text-embedding-3-small":
        # Get embeddings
        if args.drop_first_word:
            embeddings = get_embeddings(client, [' '.join(s.split()[1:]) if len(s.split()) > 1 else s for s in substeps])
        else:
            embeddings = get_embeddings(client, substeps)

        # Perform clustering
        clustering_results = perform_clustering(
            embeddings,
            k_values=k_values,
            method=clustering_method,
            min_cluster_sizes=min_cluster_sizes,
            min_samples=args.min_samples
        )

        # Generate cluster summaries
        cluster_summaries = generate_cluster_names(client, substeps, clustering_results)

    elif embedding_type == "gpt-5.2-prompted":
        # Use GPT to directly categorize substeps
        clustering_results = {}
        cluster_summaries = {}

        for k in tqdm(k_values, desc="GPT-5.2 prompted categorization"):
            substep_to_category = gpt_prompted_categorization(client, substeps, k)
            labels, cluster_info = transform_gpt_categorization_to_clustering_format(
                substeps, substep_to_category
            )
            clustering_results[k] = labels
            cluster_summaries[k] = cluster_info

    elif embedding_type == "all":
        # Run both methods
        print("\n--- Running text-embedding-3-small method ---")
        if args.drop_first_word:
            embeddings = get_embeddings(client, [' '.join(s.split()[1:]) if len(s.split()) > 1 else s for s in substeps])
        else:
            embeddings = get_embeddings(client, substeps)
        clustering_results_embedding = perform_clustering(
            embeddings,
            k_values=k_values,
            method=clustering_method,
            min_cluster_sizes=min_cluster_sizes,
            min_samples=args.min_samples
        )
        cluster_summaries_embedding = generate_cluster_names(
            client, substeps, clustering_results_embedding
        )

        print("\n--- Running gpt-5.2-prompted method ---")
        clustering_results_gpt = {}
        cluster_summaries_gpt = {}

        for k in tqdm(k_values, desc="GPT-5.2 prompted categorization"):
            substep_to_category = gpt_prompted_categorization(client, substeps, k)
            labels, cluster_info = transform_gpt_categorization_to_clustering_format(
                substeps, substep_to_category
            )
            clustering_results_gpt[k] = labels
            cluster_summaries_gpt[k] = cluster_info

        # Export both results with different filenames
        output_file_embedding = output_file.parent / f"clustering_results_embedding_{clustering_method}{param_suffix}.json"
        output_file_gpt = output_file.parent / f"clustering_results_gpt_{clustering_method}{param_suffix}.json"

        export_results(
            substeps,
            original_data,
            clustering_results_embedding,
            cluster_summaries_embedding,
            str(output_file_embedding),
            method="text-embedding-3-small",
            clustering_method=clustering_method,
        )
        export_results(
            substeps,
            original_data,
            clustering_results_gpt,
            cluster_summaries_gpt,
            str(output_file_gpt),
            method="gpt-5.2-prompted",
            clustering_method=clustering_method,
        )

        print("\n" + "=" * 60)
        print("Analysis complete!")
        print("=" * 60)
        return

    # Export results
    export_results(
        substeps,
        original_data,
        clustering_results,
        cluster_summaries,
        str(output_file),
        method=embedding_type,
        clustering_method=clustering_method
    )

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
