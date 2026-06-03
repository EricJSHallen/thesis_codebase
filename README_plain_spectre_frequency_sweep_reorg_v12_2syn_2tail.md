# Plain Spectre frequency sweep reorg v12, 2-synapse / 2-tail variant

This bundle is derived from the working v12 plain-Spectre flow, but targets the `dynapsetb1` two-synapse testbench used by `pwl_2syn.ocn` / `2syn_2tail.ocn`.

Expected exported column order in each `output_signals.txt`:

```text
iout_172 iout_56 vpre vpre1
```

That is: two output currents, then two input voltages.

## Install

Extract from the repository root:

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
tar -xzf plain_spectre_frequency_sweep_reorg_v12_2syn_2tail.tar.gz
```

## Prepare a run

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase
NUM_JOBS=4 RUN_LABEL=2syn_2tail_plain \
./experiments/frequency_sweep/bin/spectre_sweep_plain_reorg_v12_2syn_2tail.sh prep
```

The prep script will print the generated run directory, typically:

```text
/home/s5117909/Documents/thesis/thesis_codebase/database/<timestamp>_2syn_2tail_plain
```

## Run

```bash
cd /home/s5117909/Documents/thesis/thesis_codebase/database/<timestamp>_2syn_2tail_plain
./import_template.sh
./refresh_spectre_runtime.sh
source ./setup_spectre_env.sh
check_spectre_runtime
check_export_runtime
./run_all_workers.sh
./monitoring_commands.sh progress
```

## Important defaults

This variant defaults to the two-synapse Cadence netlist source:

```bash
NETLIST_SOURCE=/home/s5117909/simulation/dynapsetb1/spectre/schematic/netlist
ADE_E_SOURCE=/home/s5117909/simulation/dynapsetb1/spectre/schematic/netlist/ade_e.scs
```

Override those variables when running the prep script if your Cadence simulation directory differs.

The flow deliberately does not add `strobeperiod`.
