#!/bin/bash
#SBATCH --job-name=buildrix
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=12:00:00
#SBATCH --array=0-3
#SBATCH --output=buildrix-%A_%a.log

set -euo pipefail
# Set your partition/account above and activate your Python environment here.
# Prepare the bundle with execution.backend=apptainer and a shared SIF path.
# Inject provider API keys through your cluster's approved credential mechanism.
# All shards must use the same shared bundle and results directories.
buildrix benchmark batch --bundle bundle --output results --offline \
  --shard-index "${SLURM_ARRAY_TASK_ID}" --shard-count 4

# After the array finishes, on a host signed in to the same Buildrix hub:
# buildrix benchmark sync --output results
