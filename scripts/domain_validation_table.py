#!/usr/bin/env python3

from pathlib import Path


def main():
    # Get all the files that are called output_cc.txt inside of exp/domain_validation
    exp_dir = Path("exp/domain_validation")
    output_files = list(exp_dir.glob("**/output_cc.txt"))
    output_files.sort()

    d = {}

    for file in output_files:
        # Get scenario, instance and model name
        scenario = file.parent.parent.parent.parent.name
        instance = file.parent.parent.parent.name
        model = file.parent.parent.name

        if scenario not in d:
            d[scenario] = {}
        if instance not in d[scenario]:
            d[scenario][instance] = {}
        if model not in d[scenario][instance]:
            d[scenario][instance][model] = {"HL": False, "LL": False} # False means evaluated wrong, True means evaluated correctly, N/A means not evaluated
        
        # For each file, read the content. The content should contain one line starting with "HL: VERDICT" and one starting with "VERDICT". Print the result of the first line as "HL DV: " and the second line as "LL DV: ", plus the verdict after it. If there is only one line, print "LL DV: N/A"
        with open(file, "r") as f:
            if "incorrect" in instance:
                text = f.read()
                if scenario == "blocks_world":
                    if instance in ["2_incorrect", "5_incorrect"]:
                        if text.count("VERDICT") > 1:
                            d[scenario][instance][model] = {"HL": False, "LL": False}
                        elif "VERDICT: PROBLEM" in text:
                            d[scenario][instance][model] = {"HL": True, "LL": True}
                        elif "HL: VERDICT: OK" in text:
                            d[scenario][instance][model] = {"HL": False, "LL": False}

                    elif instance == "3_incorrect":
                        if "HL: VERDICT: OK" not in text:
                            d[scenario][instance][model] = {"HL": False, "LL": False}
                        elif "HL: VERDICT: OK" in text:
                            if "VERDICT: PROBLEM" in text:
                                d[scenario][instance][model] = {"HL": True, "LL": True}
                            else:
                                d[scenario][instance][model] = {"HL": True, "LL": False}

                elif scenario == "grippers":
                    if instance == "1_incorrect":
                        if "HL: VERDICT: OK" not in text:
                            d[scenario][instance][model] = {"HL": False, "LL": False}
                        elif "HL: VERDICT: OK" in text:
                            if "VERDICT: PROBLEM" in text:
                                d[scenario][instance][model] = {"HL": True, "LL": True}
                            else:
                                d[scenario][instance][model] = {"HL": True, "LL": False}
                else:
                    print(f"Special case not found for {scenario} {instance} {model}")
            else: 
                lines = f.readlines()
                for line in lines:
                    if "HL: VERDICT: OK" in line:
                        d[scenario][instance][model]["HL"] = True
                    elif "VERDICT: OK" in line:
                        d[scenario][instance][model]["LL"] = True

    print('', end="                ")
    for scenario in d:
        for instance in d[scenario]:
            if "incorrect" in instance:
                print(f" {instance.split('_')[0]}.b ", end="&")
            else:
                print(f"  {instance}  ", end="&")

    print(" \\\\")

    for model in ["azure_claude-opus46-multi", "azure_claude-sonnet46-multi", "azure_gpt52-multi", "azure_gpt54-mini-multi", "hf_Qwen_Qwen3.6-35B-A3B-multi", "hf_meta-llama_Llama-3.3-70B-Instruct-multi", "hf_mistralai_Mixtral-8x7B-Instruct-v0.1-multi"]:
        if "opus" in model:
            print(f"{'Opus 4.6':<14}", end=" &")
        if "sonnet" in model:
            print(f"{'Sonnet 4.6':<14}", end=" &")
        if "gpt52" in model:
            print(f"{'GPT-5.2':<14}", end=" &")
        if "gpt54" in model:
            print(f"{'GPT-5.4 Mini':<14}", end=" &")
        if "Qwen" in model:
            print(f"{'Qwen 3.6':<14}", end=" &")
        if "Llama" in model:
            print(f"{'Llama 3.3':<14}", end=" &")
        if "Mixtral" in model:
            print(f"{'Mixtral':<14}", end=" &")

        for scenario in d:
            for instance in d[scenario]:
                if model in d[scenario][instance]:
                    hl = d[scenario][instance][model]["HL"] 
                    ll = d[scenario][instance][model]["LL"] 
                    if hl and ll:
                        print(" \\cm &", end="")
                    elif not hl:
                        print(" \\wh &", end="")
                    elif hl and not ll:
                        print(" \\wl &", end="")
        print(" \\\\")


if __name__ == "__main__":
    main()