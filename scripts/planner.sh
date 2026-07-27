#!/usr/bin/env bash

proj_dir=$(realpath "$(dirname "$0")/..")

run_planner_test() {
    BASE_DIR="${proj_dir}/tmp/kb_generation/$1/$3/$2"
    KB_FILE="${BASE_DIR}/output/kb_ll.pl"
    MAX_DEPTH=2
    TIMEOUT=1500
    OUTPUT_DIR="${proj_dir}/tmp/planner_output"

    python3 "${proj_dir}/TP/planner.py" \
        --kb ${KB_FILE} \
        --save-log ${OUTPUT_DIR}/planner.log \
        --save-prolog-log ${OUTPUT_DIR}/prolog_planner.log \
        --max-depth ${MAX_DEPTH} \
        --timeout ${TIMEOUT} \
        --po-html ${OUTPUT_DIR}/po_graph.html \
        --stn-html ${OUTPUT_DIR}/stn_graph.html \
        --optimize-stn \
        --optimize-objective=end_time \
        --opt-stn-html ${OUTPUT_DIR}/optimized_stn.html \
        --bt-xml ${OUTPUT_DIR}/optimized_bt.xml \
        --optimize-infeasibility-report ${OUTPUT_DIR}/stn_infeasibility_report.txt \
        --bt-save-viz ${OUTPUT_DIR}/bt_viz.html \
        --profile &> ${OUTPUT_DIR}/planner_profile.log
}

if [[ -z "${CONDA_DEFAULT_ENV}" || "${CONDA_DEFAULT_ENV}" != "PLANTOR" ]]; then
    echo "Please activate the PLANTOR conda environment before running this script."
    read -p "Press Enter to continue or Ctrl+C to cancel..."
fi

for scenario in "blocks_world" "grippers"; do
    for model in "azure_gpt52" "azure_gpt54-mini" "azure_claude-opus46" "azure_claude-sonnet46"; do
        for test_n in 1 2 3 4 5 6; do
            run_planner_test "${scenario}" "${model}" "${test_n}" 
            echo -e "\n\n\n\n\n\n\n\n\n\n"
        done
    done
done

