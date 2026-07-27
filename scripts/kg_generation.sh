#!/bin/bash

proj_dir=$(realpath "$(dirname "$0")/..")

run_model_query() {
	local scenario="$1"
	local model="$2"
	local test_n="$3"
	shift 3

	local test_dir="${proj_dir}/tmp/kb_generation/${scenario}/${test_n}"
	local model_dir="${test_dir}/${model}-multi"
	local query_dir="${test_dir}/query"

	if [ -d "${model_dir}" ]; then
		echo "Model directory ${model_dir} exist. Skipping."
		return
	fi

	mkdir -p "${model_dir}/output"

	echo "Running ${proj_dir}/KMS/LLM/llm_gen.py with model ${model} for test ${test_n} with additional args: $@"

		# --only-comprehension \
	python3 "${proj_dir}/KMS/LLM/llm_gen.py" \
		--query-hl-file "${query_dir}/query_hl.txt" \
		--query-ll-file "${query_dir}/query_ll.txt" \
		--log-file "${model_dir}/log.log" \
		--output-path "${model_dir}/output" \
		--conf "${proj_dir}/KMS/LLM/conf/${model}.yaml" \
		"$@"
}

if [[ -z "${CONDA_DEFAULT_ENV}" || "${CONDA_DEFAULT_ENV}" != "PLANTOR" ]]; then
	echo "Please activate the PLANTOR conda environment before running this script."
	read -p "Press Enter to continue or Ctrl+C to cancel..."
fi

for scenario in "blocks_world"; do
	for model in "azure_gpt52" "azure_gpt54-mini" "azure_claude-opus46" "azure_claude-sonnet46"; do
		for test_n in 1; do
			run_model_query "${scenario}" "${model}" "${test_n}" $@
			echo -e "\n\n\n\n\n\n\n\n\n\n"
		done
	done
done





