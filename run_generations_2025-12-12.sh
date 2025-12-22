#!/bin/bash

# Task generation script for 2025-12-12
# Loops through tasks from data/tasks/2025-12-11.txt
# Generates 5 runs per task for openrouter, then 5 runs per task for openai

echo "Starting task generation batch for 2025-12-12"
echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Running 5 iterations per task for openrouter, then 5 for openai"
echo "=========================================="

# Array of task descriptions from data/tasks/2025-12-11.txt
declare -a TASKS=(
    "Push the box to the taped square on the floor"
    "Carry the box onto the rug near the doorway"
    "Slide the box under the table without tipping it"
    "Place the box on the chair seat centered"
    "Move the box beside the sofa against the wall"
    "Rotate the box to face the window then stop"
    "Put the box on the shelfs lowest level"
    "Pull the box out from under the bed"
    "Push the box into the closet past the threshold"
    "Align the box with the hallway arrow on the floor"
)

# Providers to use
# declare -a PROVIDERS=("openrouter" "openai")
declare -a PROVIDERS=("openai")

# Loop through each provider
for PROVIDER in "${PROVIDERS[@]}"; do
    echo ""
    echo "=========================================="
    echo "Starting generation with provider: $PROVIDER"
    echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="

    # Loop through each task
    for i in "${!TASKS[@]}"; do
        TASK_NUM=$((i + 1))
        TASK_DESC="${TASKS[$i]}"

        # Run 5 times for each task
        for RUN in {1..2}; do
            echo ""
            echo "[$(date '+%H:%M:%S')] [$PROVIDER] Task $TASK_NUM/10 - Run $RUN/5: $TASK_DESC"
            echo "----------------------------------------"

            uv.exe run modal run --detach robogen_modal_conda_with_apis.py \
                --task-description "$TASK_DESC" \
                --target-model-provider "$PROVIDER" \
                --generate-task

            # Small delay between submissions
            sleep 2
        done
    done
done

echo ""
echo "=========================================="
echo "All tasks submitted!"
echo "Completed at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Total: 10 tasks × 5 runs × 2 providers = 100 generations"
echo "Use 'modal app logs' to monitor progress"
