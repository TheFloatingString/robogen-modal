import modal
import os

# Create Modal app
app = modal.App("robogen")

# Define the Modal image with CUDA 11.8 support and all necessary dependencies
image = (
    modal.Image.from_registry(
        "nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04", add_python="3.9"
    )
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
    )
    .pip_install(
        "pybullet",
        "gymnasium",
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "opencv-python",
        "pillow",
        "scikit-learn",
        "scikit-image",
        "transformers",
        "sentence-transformers",
        "openai",
        "pyyaml",
        "trimesh",
        "networkx",
        "shapely",
        "rtree",
        "imageio",
        "tqdm",
        "ray[rllib]",
        "stable-baselines3",
    )
    .pip_install(
        "torch==2.0.0+cu118",
        "torchvision==0.15.0+cu118",
        extra_index_url="https://download.pytorch.org/whl/cu118",
    )
    .run_commands(
        "git clone https://github.com/TheFloatingString/RoboGen-fork.git /root/RoboGen",
        "pip install /root/RoboGen/ompl-1.6.0*.whl",
    )
)


@app.function(
    image=image,
    gpu="T4",
    secrets=[modal.Secret.from_dict({"OPENAI_API_KEY": ""})],
    timeout=3600,
)
def run_prompt_from_description():
    """Run the prompt_from_description.py command"""
    import subprocess
    import sys

    os.chdir("/root/RoboGen")

    # Add RoboGen to Python path so gpt_4 module can be imported
    env = os.environ.copy()
    env["PYTHONPATH"] = "/root/RoboGen"

    cmd = [
        "python",
        "gpt_4/prompts/prompt_from_description.py",
        "--task_description",
        "Put a pen into the box",
        "--object",
        "Box",
    ]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    print("STDOUT:")
    print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    print(f"Return code: {result.returncode}")

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


@app.function(
    image=image,
    gpu="T4",
    secrets=[modal.Secret.from_dict({"OPENAI_API_KEY": ""})],
    timeout=3600,
)
def run_execute():
    """Run the execute.py command"""
    import subprocess

    os.chdir("/root/RoboGen")

    cmd = [
        "python",
        "execute.py",
        "--task_config_path",
        "example_tasks/Change_Lamp_Direction/Change_Lamp_Direction_The_robotic_arm_will_alter_the_lamps_light_direction_by_manipulating_the_lamps_head.yaml",
    ]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    print("STDOUT:")
    print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    print(f"Return code: {result.returncode}")

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


@app.local_entrypoint()
def main():
    """Run both commands sequentially"""
    print("=" * 80)
    print("Running prompt_from_description.py")
    print("=" * 80)
    result1 = run_prompt_from_description.remote()
    print(f"\nFirst command completed with return code: {result1['returncode']}\n")

    print("=" * 80)
    print("Running execute.py")
    print("=" * 80)
    result2 = run_execute.remote()
    print(f"\nSecond command completed with return code: {result2['returncode']}\n")

    print("=" * 80)
    print("All commands completed!")
    print("=" * 80)
