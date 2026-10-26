#!/usr/bin/env bash
set -eo pipefail
source /opt/openfoam14/etc/bashrc

level="${1:-coarse}"
case "$level" in
    coarse|medium|fine) ;;
    *) echo "Usage: $0 [coarse|medium|fine]" >&2; exit 2 ;;
esac

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
run_dir="${FOAM_RUN}/nasa-tmr-backstep-${level}-$(date -u +%Y%m%dT%H%M%SZ)"
case_dir="${run_dir}/case"
mkdir -p "$run_dir"
cp -R "${repo_root}/cases/nasa-tmr-backstep" "$case_dir"
python3 "${repo_root}/scripts/generate_block_mesh.py" \
    --level "$level" \
    --output "${case_dir}/system/blockMeshDict"

cd "$case_dir"
foamVersion > "${run_dir}/environment.txt"
dpkg-query -W openfoam14 >> "${run_dir}/environment.txt"
sha256sum system/blockMeshDict 0/U 0/p 0/nuTilda 0/nut constant/physicalProperties constant/momentumTransport \
    system/controlDict system/fvSchemes system/fvSolution system/functions system/meshQualityDict \
    > "${run_dir}/input-sha256.txt"
blockMesh 2>&1 | tee "${run_dir}/log.blockMesh"
checkMesh -allTopology -allGeometry -meshQuality 2>&1 | tee "${run_dir}/log.checkMesh"
foamRun 2>&1 | tee "${run_dir}/log.foamRun"
python3 "${repo_root}/scripts/analyze_results.py" \
    --run-dir "$run_dir" \
    --reference-dir "${repo_root}/data/reference" \
    --output "${run_dir}/result.json"
printf 'Run directory: %s\n' "$run_dir"
