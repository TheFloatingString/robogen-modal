for i in seq 1 10 do
    uv run modal run --detach robogen_modal_conda_with_apis.py --task-description "rotate the box to face the window" --target-model-provider novita --generate-task
end