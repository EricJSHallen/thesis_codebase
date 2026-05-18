#!/bin/bash

set -x

OCN="/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/single_pwl_opt_parallel.ocn"
LOGDIR="/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction"

echo "Starting test at $(date)"
echo "OCN=$OCN"
echo "LOGDIR=$LOGDIR"
echo "PATH=$PATH"

echo "Checking files:"
ls -lh "$OCN"
ls -ld "$LOGDIR"

echo "Checking ocean:"
which ocean
type ocean

echo "Launching one OCEAN job..."

CAD_NUM_JOBS=4 CAD_JOB_INDEX=0 ocean -nograph -restore "$OCN" > "$LOGDIR/ocean_test_job0.log" 2>&1 &

PID=$!
echo "Started background PID=$PID"

sleep 5

echo "Checking whether PID is still alive:"
ps -p "$PID" -f

echo "First 80 lines of ocean log:"
head -80 "$LOGDIR/ocean_test_job0.log"

echo "Test launcher finished at $(date)"