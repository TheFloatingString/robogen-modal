# RoboGen Modal

This project runs RoboGen tasks on Modal with GPU support.

## Usage

**To run RoboGen, use `robogen_modal_conda.py` (this is the goto file):**

```bash
modal run robogen_modal_conda.py
```

This script will:
1. Build a Docker image with CUDA 11.8 and Python 3.9
2. Install micromamba (lightweight conda alternative)
3. Clone the RoboGen repository
4. Create conda environment from RoboGen's environment.yaml
5. Install additional packages (anthropic, groq, pybullet, ray)
6. Install the ompl wheel (version 1.6.0)
7. Run the RoboGen tasks:
   - `prompt_from_description.py` - Generate task descriptions
   - `execute.py` - Execute the robotic tasks

## Requirements

- Modal account and CLI installed
- Access to GPU resources (T4)
