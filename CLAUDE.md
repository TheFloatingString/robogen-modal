### For generating tasks

```bash
uv run modal run --detach robogen_modal_conda_with_apis.py --task-description "[[task description]]" --target-model-provider [[either "novita" for "openai"]] --generate-task
```

### For executing tasks (policy training)

```bash
uv run modal run --detach robogen_modal_conda_with_apis.py --task-config-path "./data/generated_task_from_description/[[folder]]//[[config file]]" --execute
```

Always do the following
- if `pyproject.toml` is present, use `uv run <filename.py>` and `uv` to run files
- preface any modal commands in the cli with: `export PYTHONIOENCODING="utf-8"; modal ...`
- always use the `--detach` flag for modal cli commands, unless specified otherwise. use optional commands in model like `uv run modal run [OPTIONS] <filename.py>`

Run the following on Modal:

- The partnet `dataset` folder should be unzipped from https://drive.google.com/file/d/1d-1txzcg_ke17NkHKAolXlfDnmPePFc6/view and then put under `./data/dataset`
- the embeddings should be put under `./objaverse_utils/data/` from https://drive.google.com/file/d/1dFDpG3tlckTUSy7VYdfkNqtfVctpn3T6/view
