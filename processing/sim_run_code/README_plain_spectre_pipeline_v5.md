# Plain Spectre pipeline v5

This version fixes a failure seen in generated run folders where helper scripts
such as `run_all_workers.sh`, `run_spectre_worker.sh`, and `setup_spectre_env.sh`
were malformed with collapsed newlines. In that state, `run_all_workers.sh` can
appear to hang or do nothing, and worker logs stay empty.

v5 changes:

1. Generates helper scripts with normal multiline here-documents.
2. Calls workers with `bash run_spectre_worker.sh` rather than relying on the shebang.
3. Adds a post-generation sanity check: if helper scripts have too few lines, prep fails immediately.
4. Keeps the v4 Spectre runtime-library search fix.

Install:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
cp /mnt/data/spectre_sweep_plain_v5.sh processing/sim_run_code/spectre_sweep_plain_v5.sh
chmod +x processing/sim_run_code/spectre_sweep_plain_v5.sh
```

Prepare:

```bash
NUM_JOBS=4 RUN_LABEL=2channel_1syn_plain \
./processing/sim_run_code/spectre_sweep_plain_v5.sh prep
```

Then:

```bash
cd thesis_database/<new_run_id>
./run_template_ocean.sh
./import_template.sh
./run_all_workers.sh
./monitoring_commands.sh progress
```

Before running workers, verify helper scripts are sane:

```bash
wc -l run_all_workers.sh run_spectre_worker.sh setup_spectre_env.sh select_cases.py monitoring_commands.sh
head -5 run_all_workers.sh
head -5 run_spectre_worker.sh
```

Expected: `run_all_workers.sh` should be multiple lines, `run_spectre_worker.sh`
should be many lines, not 1-2 lines.
