# simprep_isolated_netlist_v9.sh

This is the current clean-run helper for the Cadence/OCEAN IPC workflow.

Fixes included:

- avoids `thesis_codebase/thesis_codebase` when the outer repo is the correct one;
- uses `envSetVal("asimenv.startup" "projectDir" 'string ...)`, not the invalid `projectDir(...)`;
- creates per-job Cadence project directories;
- generates a per-run `run_ocean_job.sh` wrapper;
- the wrapper starts an `ade_e.scs` symlink helper before OCEAN, so newly created isolated netlist directories get `ade_e.scs` automatically;
- writes `ciw_commands.il`, `monitoring_commands.sh`, `RUNINFO.txt`, logs, and outputs inside the run directory.

Basic use:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
cp /path/to/simprep_isolated_netlist_v9.sh processing/sim_run_code/
chmod +x processing/sim_run_code/simprep_isolated_netlist_v9.sh

NUM_JOBS=4 RUN_LABEL=2channel_1syn \
./processing/sim_run_code/simprep_isolated_netlist_v9.sh
```

Then paste the generated CIW commands into CIW.

Monitor from the run directory:

```bash
./monitoring_commands.sh progress
```

If the script cannot locate `ade_e.scs`, provide it explicitly:

```bash
ADE_E_SOURCE=/home/s5117909/simulation/synapsedualinputtb/spectre/schematic/netlist/ade_e.scs \
NUM_JOBS=4 RUN_LABEL=2channel_1syn \
./processing/sim_run_code/simprep_isolated_netlist_v9.sh
```
