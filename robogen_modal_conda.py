import modal
import os
import argparse

# Hardcoded API keys
NOVITA_API_KEY = os.getenv('NOVITA_API_KEY') 
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') 
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") 
WANDB_API_KEY = os.getenv("WANDB_API_KEY")

# Create Modal app
app = modal.App("robogen-conda")

# Create persistent volumes for data storage
dataset_volume = modal.Volume.from_name("robogen-dataset", create_if_missing=True)
embeddings_volume = modal.Volume.from_name("robogen-embeddings", create_if_missing=True)
outputs_volume = modal.Volume.from_name("robogen-generated_task_outputs", create_if_missing=True)
models_cache_volume = modal.Volume.from_name("robogen-models-cache", create_if_missing=True)

# Define the Modal image with CUDA 11.8, micromamba, and RoboGen setup
image = (
    modal.Image.from_registry("nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04", add_python="3.9")
    .apt_install(
        "git",
        "wget",
        "build-essential",
        "cmake",
        "libboost-all-dev",
        "libeigen3-dev",
        "libode-dev",
        "pkg-config",
        "libgl1-mesa-glx",
        "libglib2.0-0",
        "curl",
        "bzip2",
        "ca-certificates",
        "unzip",
    )
    .run_commands(
        # Install micromamba (lightweight conda alternative)
        "curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba",
        "mv bin/micromamba /usr/local/bin/",
        "mkdir -p /opt/conda",
    )
    .run_commands(
        # Clone RoboGen repository and checkout specific commit
        "git clone https://github.com/TheFloatingString/RoboGen-fork.git /root/RoboGen",
        "cd /root/RoboGen && git checkout 9920fa4e4758c1e1baab4fa50bac2c60e3459311",
    )
    .run_commands(
        # Create conda environment from environment.yaml
        "cd /root/RoboGen && micromamba create -f environment.yaml -p /opt/conda/envs/robogen -y",
    )
    .run_commands(
        # Install additional required packages
        "/opt/conda/envs/robogen/bin/pip install anthropic groq python-dotenv pybullet ray[rllib] gdown tqdm",
    )
    .run_commands(
        # Install ompl wheel
        "/opt/conda/envs/robogen/bin/pip install /root/RoboGen/ompl-1.6.0*.whl",
    )
)

@app.function(
    image=image,
    volumes={"/data": dataset_volume},
    timeout=3600,
)
def setup_dataset():
    """Download and unzip the PartNet dataset to the volume"""
    import subprocess
    import sys

    print("=" * 80)
    print("SETTING UP DATASET VOLUME")
    print("=" * 80)

    # Check if dataset already exists
    if os.path.exists("/data/dataset") and os.listdir("/data/dataset"):
        print("✓ Dataset already exists, skipping download")
        return {"status": "already_exists"}

    # Create data directory
    os.makedirs("/data", exist_ok=True)

    # Set up environment to use conda
    env = os.environ.copy()
    env["PATH"] = f"/opt/conda/envs/robogen/bin:{env['PATH']}"

    # Download dataset from Google Drive with progress bar
    print("\n[1/3] Downloading dataset from Google Drive...")
    print("      This may take several minutes depending on file size...")
    file_id = "1d-1txzcg_ke17NkHKAolXlfDnmPePFc6"
    output_file = "/data/dataset.zip"

    cmd = [
        "/opt/conda/envs/robogen/bin/gdown",
        f"https://drive.google.com/uc?id={file_id}",
        "-O", output_file,
        "--fuzzy"  # Better handling of Google Drive downloads
    ]

    # Run with real-time output to show gdown's built-in progress
    result = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    for line in result.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()

    result.wait()

    if result.returncode != 0:
        return {"status": "download_failed", "error": "Download failed, check logs above"}

    print("\n✓ Download complete!")

    # Get file size for progress indication
    file_size = os.path.getsize(output_file)
    print(f"\n[2/3] Unzipping dataset ({file_size / (1024**3):.2f} GB)...")

    # Unzip with verbose output to show progress
    unzip_cmd = ["unzip", "-o", output_file, "-d", "/data"]
    unzip_result = subprocess.Popen(
        unzip_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    print("      Extracting files...")
    file_count = 0
    for line in unzip_result.stdout:
        if "inflating:" in line or "extracting:" in line:
            file_count += 1
            if file_count % 100 == 0:  # Print every 100 files
                print(f"      Extracted {file_count} files...")
                sys.stdout.flush()

    unzip_result.wait()

    if unzip_result.returncode != 0:
        return {"status": "unzip_failed", "error": "Unzip failed, check logs above"}

    print(f"✓ Extracted {file_count} files successfully!")

    # Clean up zip file
    print("\n[3/3] Cleaning up...")
    if os.path.exists(output_file):
        os.remove(output_file)
        print("✓ Removed zip file")

    # Commit volume changes
    print("\n⟳ Committing volume changes...")
    dataset_volume.commit()
    print("✓ Dataset setup complete and volume committed!")
    print("=" * 80)

    return {"status": "success", "files_extracted": file_count}


@app.function(
    image=image,
    volumes={"/embeddings_data": embeddings_volume},
    timeout=3600,
)
def setup_embeddings():
    """Download embeddings to the volume"""
    import subprocess
    import sys

    print("=" * 80)
    print("SETTING UP EMBEDDINGS VOLUME")
    print("=" * 80)

    # Check if the actual embeddings file exists (not just the zip)
    embeddings_file = "/embeddings_data/partnet_mobility_category_embeddings.pt"
    if os.path.exists(embeddings_file):
        print("✓ Embeddings already exist, skipping download")
        file_size = os.path.getsize(embeddings_file)
        print(f"  Found: partnet_mobility_category_embeddings.pt ({file_size / (1024**2):.2f} MB)")
        return {"status": "already_exists"}

    # Create embeddings directory
    os.makedirs("/embeddings_data", exist_ok=True)

    # Set up environment to use conda
    env = os.environ.copy()
    env["PATH"] = f"/opt/conda/envs/robogen/bin:{env['PATH']}"

    # Download embeddings from Google Drive with progress bar
    print("\n[1/2] Downloading embeddings from Google Drive...")
    print("      This may take several minutes depending on file size...")
    file_id = "1dFDpG3tlckTUSy7VYdfkNqtfVctpn3T6"

    cmd = [
        "/opt/conda/envs/robogen/bin/gdown",
        f"https://drive.google.com/uc?id={file_id}",
        "-O", "/embeddings_data/",
        "--fuzzy"  # Better handling of Google Drive downloads
    ]

    # Run with real-time output to show gdown's built-in progress
    result = subprocess.Popen(
        cmd,
        env=env,
        cwd="/embeddings_data",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    for line in result.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()

    result.wait()

    if result.returncode != 0:
        return {"status": "download_failed", "error": "Download failed, check logs above"}

    print("\n✓ Download complete!")

    # Check if downloaded file is a zip and unzip it
    print("\n[2/3] Checking for zip file...")
    downloaded_files = os.listdir("/embeddings_data")
    zip_file = None
    for file in downloaded_files:
        if file.endswith('.zip'):
            zip_file = f"/embeddings_data/{file}"
            break

    if zip_file:
        print(f"Found zip file: {os.path.basename(zip_file)}")
        print("Unzipping embeddings...")

        unzip_cmd = ["unzip", "-o", zip_file, "-d", "/embeddings_data"]
        unzip_result = subprocess.run(
            unzip_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        if unzip_result.returncode != 0:
            print(f"Unzip output: {unzip_result.stdout}")
            return {"status": "unzip_failed", "error": "Unzip failed, check logs above"}

        print("✓ Unzip complete!")

        # Remove zip file after extraction
        os.remove(zip_file)
        print(f"✓ Removed zip file")

    # List downloaded files
    print("\n[3/3] Verifying downloaded files...")
    downloaded_files = os.listdir("/embeddings_data")
    for file in downloaded_files:
        file_path = f"/embeddings_data/{file}"
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)
            print(f"      ✓ {file} ({file_size / (1024**2):.2f} MB)")

    # Commit volume changes
    print("\n⟳ Committing volume changes...")
    embeddings_volume.commit()
    print("✓ Embeddings setup complete and volume committed!")
    print("=" * 80)

    return {"status": "success", "files": downloaded_files}


@app.function(
    image=image,
    gpu="T4",
    volumes={
        "/data": dataset_volume,
        "/embeddings_data": embeddings_volume,
        "/outputs": outputs_volume,
        "/root/.cache": models_cache_volume  # Cache for Hugging Face & Torch models
    },
    secrets=[modal.Secret.from_dict(
        {
            "OPENAI_API_KEY": OPENAI_API_KEY,
            "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
            "NOVITA_API_KEY": NOVITA_API_KEY,
            "WANDB_API_KEY": WANDB_API_KEY
        }
    )],
    timeout=3600,
)
def run_prompt_from_description(target_model_provider: str = "novita", task_description: str = "Put a pen into the box"):
    """Run the prompt_from_description.py command"""
    import subprocess
    import shutil

    os.chdir("/root/RoboGen")

    # Create symlinks to mounted volumes in expected locations
    print("Setting up data paths...")
    os.makedirs("/root/RoboGen/data", exist_ok=True)
    os.makedirs("/root/RoboGen/objaverse_utils/data", exist_ok=True)

    # Link dataset volume to expected path - always recreate to ensure it's correct
    target_path = "/root/RoboGen/data/dataset"
    if os.path.exists("/data/dataset"):
        # Remove existing symlink/directory if it exists
        if os.path.islink(target_path):
            os.unlink(target_path)
            print("  Removed old symlink")
        elif os.path.exists(target_path):
            if os.path.isdir(target_path) and not os.listdir(target_path):
                os.rmdir(target_path)
                print("  Removed empty directory")

        # Create fresh symlink
        if not os.path.exists(target_path):
            os.symlink("/data/dataset", target_path)
            print("✓ Linked dataset volume")
            # Verify the dataset has content
            dataset_items = os.listdir("/data/dataset")
            print(f"  Dataset contains {len(dataset_items)} items")
            if "100426" in dataset_items:
                print("  ✓ Found object 100426")
    else:
        print("⚠ Warning: /data/dataset not found - volume may not be set up")

    # Link embeddings files to expected path
    if os.path.exists("/embeddings_data"):
        embeddings_files = os.listdir("/embeddings_data")
        for file in embeddings_files:
            target_path = f"/root/RoboGen/objaverse_utils/data/{file}"
            source_path = f"/embeddings_data/{file}"
            if not os.path.exists(target_path):
                os.symlink(source_path, target_path)
        print(f"✓ Linked {len(embeddings_files)} embeddings file(s)")

    # Link outputs volume to generated_task_from_description directory
    generated_tasks_path = "/root/RoboGen/data/generated_task_from_description"
    if os.path.exists("/outputs"):
        # Remove if it exists as a directory or symlink
        if os.path.islink(generated_tasks_path):
            os.unlink(generated_tasks_path)
            print("  Removed old symlink")
        elif os.path.exists(generated_tasks_path):
            if os.path.isdir(generated_tasks_path):
                shutil.rmtree(generated_tasks_path)
                print("  Removed old directory")

        # Create symlink to outputs volume
        os.symlink("/outputs", generated_tasks_path)
        print("✓ Linked /root/RoboGen/data/generated_task_from_description to outputs volume")

    # Set up environment to use conda
    env = os.environ.copy()
    env["PATH"] = f"/opt/conda/envs/robogen/bin:{env['PATH']}"
    env["PYTHONPATH"] = "/root/RoboGen"
    env["TARGET_MODEL_PROVIDER"] = target_model_provider

    # Run prepare.sh first
    print("Running prepare.sh...")
    prepare_result = subprocess.run(
        ["bash", "-c", "source prepare.sh"],
        shell=False,
        capture_output=True,
        text=True,
        env=env,
        cwd="/root/RoboGen"
    )
    print("prepare.sh output:", prepare_result.stdout)
    if prepare_result.stderr:
        print("prepare.sh errors:", prepare_result.stderr)

    cmd = [
        "/opt/conda/envs/robogen/bin/python",
        "gpt_4/prompts/prompt_from_description.py",
        "--task_description",
        task_description,
        "--object",
        "Box"
    ]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    print("STDOUT:")
    print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    print(f"Return code: {result.returncode}")

    # Commit volume changes to persist outputs and model cache
    print("\n⟳ Committing volume changes...")
    outputs_volume.commit()
    models_cache_volume.commit()
    print("✓ Outputs and model cache saved to volumes!")

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }


@app.function(
    image=image,
    gpu="A10G",  # Changed from T4 to A10G for bfloat16 support
    volumes={
        "/data": dataset_volume,
        "/embeddings_data": embeddings_volume,
        "/outputs": outputs_volume,
        "/root/.cache": models_cache_volume  # Cache for Hugging Face & Torch models
    },
    secrets=[modal.Secret.from_dict(
        {
            "OPENAI_API_KEY": OPENAI_API_KEY,
            "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
            "NOVITA_API_KEY": NOVITA_API_KEY,
            "WANDB_API_KEY": WANDB_API_KEY
        }
    )],
    timeout=3600,
)
def run_execute(target_model_provider: str = "novita", task_config_path: str = None):
    """Run the execute.py command"""
    import subprocess
    import shutil

    os.chdir("/root/RoboGen")

    # Create symlinks to mounted volumes in expected locations
    print("Setting up data paths...")
    os.makedirs("/root/RoboGen/data", exist_ok=True)
    os.makedirs("/root/RoboGen/objaverse_utils/data", exist_ok=True)

    # Link dataset volume to expected path - always recreate to ensure it's correct
    target_path = "/root/RoboGen/data/dataset"
    if os.path.exists("/data/dataset"):
        # Remove existing symlink/directory if it exists
        if os.path.islink(target_path):
            os.unlink(target_path)
            print("  Removed old symlink")
        elif os.path.exists(target_path):
            if os.path.isdir(target_path) and not os.listdir(target_path):
                os.rmdir(target_path)
                print("  Removed empty directory")

        # Create fresh symlink
        if not os.path.exists(target_path):
            os.symlink("/data/dataset", target_path)
            print("✓ Linked dataset volume")
            # Verify the dataset has content
            dataset_items = os.listdir("/data/dataset")
            print(f"  Dataset contains {len(dataset_items)} items")
            if "100426" in dataset_items:
                print("  ✓ Found object 100426")
    else:
        print("⚠ Warning: /data/dataset not found - volume may not be set up")

    # Link embeddings files to expected path
    if os.path.exists("/embeddings_data"):
        embeddings_files = os.listdir("/embeddings_data")
        for file in embeddings_files:
            target_path = f"/root/RoboGen/objaverse_utils/data/{file}"
            source_path = f"/embeddings_data/{file}"
            if not os.path.exists(target_path):
                os.symlink(source_path, target_path)
        print(f"✓ Linked {len(embeddings_files)} embeddings file(s)")

    # Link outputs volume to generated_task_from_description directory
    generated_tasks_path = "/root/RoboGen/data/generated_task_from_description"
    if os.path.exists("/outputs"):
        # Remove if it exists as a directory or symlink
        if os.path.islink(generated_tasks_path):
            os.unlink(generated_tasks_path)
            print("  Removed old symlink")
        elif os.path.exists(generated_tasks_path):
            if os.path.isdir(generated_tasks_path):
                shutil.rmtree(generated_tasks_path)
                print("  Removed old directory")

        # Create symlink to outputs volume
        os.symlink("/outputs", generated_tasks_path)
        print("✓ Linked /root/RoboGen/data/generated_task_from_description to outputs volume")

    # Set up environment to use conda
    env = os.environ.copy()
    env["PATH"] = f"/opt/conda/envs/robogen/bin:{env['PATH']}"
    env["PYTHONPATH"] = "/root/RoboGen"
    env["TARGET_MODEL_PROVIDER"] = target_model_provider

    # Run prepare.sh first
    print("Running prepare.sh...")
    prepare_result = subprocess.run(
        ["bash", "-c", "source prepare.sh"],
        shell=False,
        capture_output=True,
        text=True,
        env=env,
        cwd="/root/RoboGen"
    )
    print("prepare.sh output:", prepare_result.stdout)
    if prepare_result.stderr:
        print("prepare.sh errors:", prepare_result.stderr)

    # Use provided task_config_path or default to the hardcoded one
    if task_config_path is None:
        task_config_path = "data/generated_task_from_description/Put_a_pen_into_the_box_Box_100426_2025-10-26-02-10-04/Put_a_pen_into_the_box_The_robot_arm_opens_the_box_lid_places_a_pen_inside_the_box_and_then_closes_the_lid_again.yaml"

    cmd = [
        "/opt/conda/envs/robogen/bin/python",
        "execute.py",
        "--task_config_path",
        task_config_path
    ]

    print(f"Running command: {' '.join(cmd)}")

    # Use Popen with stderr merged into stdout for real-time streaming
    import sys
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Merge stderr into stdout for real-time interleaved output
        text=True,
        bufsize=1  # Line buffered
    )

    # Stream output in real-time
    output_lines = []
    for line in process.stdout:
        print(line, end='')  # Print immediately as it comes
        sys.stdout.flush()  # Force flush to ensure immediate display
        output_lines.append(line)

    # Wait for process to complete
    process.wait()

    print(f"\n{'='*80}")
    print(f"Return code: {process.returncode}")
    print(f"{'='*80}")

    # Commit model cache volume to persist downloaded models
    print("\n⟳ Committing model cache volume...")
    models_cache_volume.commit()
    print("✓ Model cache saved! Next run will use cached models.")

    return {
        "stdout": ''.join(output_lines),
        "stderr": "",  # stderr was merged into stdout
        "returncode": process.returncode
    }


@app.local_entrypoint()
def main(
    target_model_provider: str = "novita",
    task_description: str = "Put a pen into the box",
    generate_task: bool = False,
    execute: bool = False,
    task_config_path: str = None
):
    """
    Run RoboGen pipeline with optional step selection

    Args:
        target_model_provider: Model provider to use (novita, openai, anthropic)
        task_description: Description of the task to generate
        generate_task: Only run task generation (prompt_from_description)
        execute: Only run task execution (execute.py)
        task_config_path: Path to task config YAML file for execution (optional)
    """
    print("\n" + "=" * 80)
    print("ROBOGEN MODAL PIPELINE")
    print(f"Target Model Provider: {target_model_provider}")
    print(f"Task Description: {task_description}")
    print("=" * 80 + "\n")

    # Step 1: Setup dataset (always run)
    print("STEP 1: Setting up dataset...")
    dataset_result = setup_dataset.remote()
    if dataset_result["status"] == "already_exists":
        print("→ Dataset already configured")
    elif dataset_result["status"] == "success":
        print(f"→ Dataset setup successful! Extracted {dataset_result.get('files_extracted', 'N/A')} files")
    else:
        print(f"✗ Dataset setup failed: {dataset_result.get('error', 'Unknown error')}")
        return

    # Step 2: Setup embeddings (always run)
    print("\nSTEP 2: Setting up embeddings...")
    embeddings_result = setup_embeddings.remote()
    if embeddings_result["status"] == "already_exists":
        print("→ Embeddings already configured")
    elif embeddings_result["status"] == "success":
        print(f"→ Embeddings setup successful! Downloaded {len(embeddings_result.get('files', []))} file(s)")
    else:
        print(f"✗ Embeddings setup failed: {embeddings_result.get('error', 'Unknown error')}")
        return

    # Determine what to run based on flags
    run_generation = False
    run_execution = False

    if generate_task and not execute:
        # Only run task generation
        run_generation = True
    elif execute and not generate_task:
        # Only run execution
        run_execution = True
    elif generate_task and execute:
        # Run both generation and execution
        run_generation = True
        run_execution = True
    else:
        # Default: run everything
        run_generation = True
        run_execution = True

    # Step 3: Run prompt_from_description (task generation)
    if run_generation:
        print("\n" + "=" * 80)
        print("STEP 3: Running prompt_from_description.py")
        print("=" * 80)
        result1 = run_prompt_from_description.remote(target_model_provider, task_description)
        print(f"\n→ Completed with return code: {result1['returncode']}\n")

    # Step 4: Run execute
    if run_execution:
        print("=" * 80)
        print("STEP 4: Running execute.py")
        print("=" * 80)
        result2 = run_execute.remote(target_model_provider, task_config_path)
        print(f"\n→ Completed with return code: {result2['returncode']}\n")

    print("=" * 80)
    print("✓ ALL STEPS COMPLETED!")
    print("=" * 80)
