# Clustering Scripts

This directory contains scripts for clustering and analyzing robotic task substeps.

## run_clustering.py

Clustering analysis of robotic task substeps using OpenAI embeddings and GPT summaries.

### Features

- Multiple clustering methods:
  - **text-embedding-3-small**: Uses OpenAI embeddings with k-means clustering
  - **gpt-5.2-prompted**: Uses GPT-4o to directly categorize substeps into meaningful categories
  - **all**: Runs both methods and outputs separate result files for comparison

### Installation

Install required dependencies:

```bash
pip install openai scikit-learn numpy tqdm python-dotenv
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

Or create a `.env` file with:

```
OPENAI_API_KEY=your-api-key-here
```

### Usage

#### Basic Usage (Text Embeddings)

```bash
python run_clustering.py -f all_substeps.json
```

This uses the default `text-embedding-3-small` method with k-means clustering.

#### GPT-5.2 Prompted Categorization

```bash
python run_clustering.py -f all_substeps.json --embedding-type gpt-5.2-prompted
```

This uses GPT-4o to directly categorize substeps into k categories.

#### Run Both Methods

```bash
python run_clustering.py -f all_substeps.json --embedding-type all
```

This runs both methods and outputs two separate JSON files:
- `clustering_results_embedding.json` (text-embedding-3-small results)
- `clustering_results_gpt.json` (gpt-5.2-prompted results)

### Command Line Arguments

- `-f, --file`: Path to input JSON file (default: `all_substeps.json`)
- `--embedding-type`: Type of embedding/categorization to use
  - `text-embedding-3-small` (default): OpenAI embeddings + k-means clustering
  - `gpt-5.2-prompted`: GPT-4o direct categorization
  - `all`: Run both methods

### Input Format

The script expects a JSON file with the following structure:

```json
{
  "data": [
    {
      "dirname": "task_name",
      "substeps": [
        "substep 1",
        "substep 2",
        ...
      ]
    },
    ...
  ]
}
```

### Output Format

The script generates a `clustering_results.json` file (or two files if using `--embedding-type all`) with the following structure:

```json
{
  "metadata": {
    "total_unique_substeps": 150,
    "total_entries": 50,
    "k_values": [50],
    "method": "text-embedding-3-small",
    "embedding_model": "text-embedding-3-small",
    "summary_model": "gpt-4o"
  },
  "data": [
    {
      "dirname": "task_name",
      "substeps": [
        {
          "text": "substep 1",
          "clusters": {
            "k_50": 5
          }
        },
        ...
      ]
    },
    ...
  ],
  "cluster_summaries": {
    "k_50": {
      "cluster_0": {
        "summary": "Grasping",
        "size": 25,
        "examples": ["grasp object", "pick up item", ...]
      },
      ...
    }
  }
}
```

### Method Comparison

#### text-embedding-3-small
- Uses OpenAI's text embeddings to create vector representations of substeps
- Applies k-means clustering to group similar substeps
- GPT-4o generates summary keywords for each cluster after clustering
- Good for discovering semantic similarity patterns

#### gpt-5.2-prompted
- GPT-4o directly categorizes all substeps into k meaningful categories
- Returns a simple mapping of substep to category name
- Code transforms the mapping into clustering format (labels + cluster info)
- Good for leveraging GPT's understanding of task semantics

### Configuration

You can modify the `k_values` in the script (line 219) to cluster with different numbers of categories:

```python
k_values = [50]  # Change to [10, 20, 30] for multiple k values
```

### Example Workflow

1. Prepare your substeps JSON file
2. Run clustering with desired method:
   ```bash
   python run_clustering.py -f my_substeps.json --embedding-type gpt-5.2-prompted
   ```
3. The script will:
   - Load and deduplicate substeps
   - Perform categorization using the selected method
   - Generate category summaries
   - Export results to JSON
4. Use the output JSON for downstream analysis or visualization

### Performance Notes

- For large datasets (1000+ substeps), `gpt-5.2-prompted` may be faster as it requires only one API call per k value
- `text-embedding-3-small` requires embedding generation + multiple GPT calls for summaries
- The `all` option is useful for comparing both approaches
