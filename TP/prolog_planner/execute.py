"""
Prepare and optionally execute Prolog planner sources with configurable debug preprocessing.
"""

import subprocess
import argparse
import os
from pathlib import Path
import re 
from typing import List


def replace_include_with_content(file_path: Path, content: list, added_files = []) -> None:
    """
    Replace the ensure_loaded directive in the Prolog file with the actual content of the included file.

    Parameters
    ----------
    file_path : Path
        Path to the file being read or transformed.
    content : list
        Full text content being parsed or transformed.
    added_files : Any, optional
        Set/list tracking already-included Prolog files to avoid duplicate inclusion.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    # Avoid re-including files in cyclic include graphs.
    if file_path in added_files:
        return
    print(f"Including content from {file_path}")
    added_files.append(file_path)
    with open(file_path, "r") as f:
        lines = f.readlines()
    new_lines = []
    for line in lines:
        match = re.match(r":-\s*ensure_loaded\s*\(['\"](.*)['\"]\)\.", line)
        if match:
            included_file = match.group(1)
            included_path = file_path.parent / included_file
            if included_path.exists():
                # Inline nested includes recursively to produce a single merged source.
                replace_include_with_content(included_path.resolve(), new_lines, added_files)
            else:
                raise FileNotFoundError(f"Included file {included_path.resolve()} not found.")
        else:
            new_lines.append(line)
        
    content.extend(new_lines)


def parse_content(content: List[str], debug = False, delete_debug = False, debug_timings = False, debug_viz = False) -> str:
    """
    Parse the content of a Prolog file and modify debug statements based on the debug flag.

    Parameters
    ----------
    content : List[str]
        Full text content being parsed or transformed.
    debug : Any, optional
        Flag controlling whether debug statements remain enabled.
    delete_debug : Any, optional
        Flag controlling whether debug statements are removed instead of commented.
    debug_timings : Any, optional
        Flag controlling whether debug timings behavior is enabled.
    debug_viz : Any, optional
        Flag controlling whether debug viz behavior is enabled.

    Returns
    -------
    str
        String result produced by this function.
    """

    print(f"Parsing Prolog content with debug={debug}, delete_debug={delete_debug}, debug_timings={debug_timings}, debug_viz={debug_viz}")

    # If debug mode is enabled and command for that line starts with debug_format, then change it with only format
    tmp_content = []
    if debug:
        for line in content:
            if re.match(r".*debug_format\(.*\)*:-*", line):
                tmp_content.append(line)
            elif re.match(r".*debug_format\(.*\)*", line):
                tmp_content.append(line.replace("debug_format", "format"))
            else:
                tmp_content.append(line)

    else:
        # Otherwise go line by line and:
        # - if the line matches r"*debug_format\(.*\)\s*," then add a % before the line and a new line with just true,
        # - if the line matches r"*debug_format\(.*\)\s*," then add a % before the line,
        # - same for print_list()
        for line in content:
            if delete_debug and line.strip().startswith("%"):
                pass
            elif re.match(r".*debug_format\(.*\)\s*,", line):
                if not delete_debug:
                    line = "% " + line
                    tmp_content.append(line)
            elif re.match(r".*print_list\(.*\)\s*,", line):
                if not delete_debug:
                    line = "% " + line
                    tmp_content.append(line)
            elif re.match(r"print_list\(\[\], \_\)\.", line):
                tmp_content.append(line)
            elif re.match(r".*debug_format\(.*\)\.", line):
                line = "% " + line
                tmp_content.append(line)
                tmp_content.append("true.\n")
            elif re.match(r".*print_list\(.*\)\.", line):
                line = "% " + line
                tmp_content.append(line)
                tmp_content.append("true.\n")
            elif re.match(r".*debug_format\(.*\)\s*:-", line):
                tmp_content.append(line)
            elif re.match(r".*debug_format\(.*\)", line):
                if not delete_debug:
                    line = "% " + line
                    tmp_content.append(line)
                tmp_content.append("true\n")
            elif re.match(r".*print_list\(.*\)\s*:-", line):
                tmp_content.append(line)
            elif re.match(r".*print_list\(.*\)", line):
                if not delete_debug:
                    line = "% " + line
                    tmp_content.append(line)
                tmp_content.append("true\n")


            # Time debugging statements
            elif re.match(r".*time_.*\(.*\)\s*", line):
                if debug_timings:
                    tmp_content.append(line)
                else:
                    if re.match(r".*time_emit\(.*\)\s*,", line):
                        if not delete_debug:
                            line = "% " + line
                            tmp_content.append(line)
                    elif re.match(r".*time_emit\(.*\)\.", line):
                        if not delete_debug:
                            line = "% " + line
                            tmp_content.append(line)
                        tmp_content.append("true.\n")
                    elif re.match(r".*time_call\(.*\)\s*:-", line):
                        tmp_content.append(line)
                    
                    # time_call works differently because we need to keep the predicate that is called inside it. 
                    elif re.match(r".*time_call\((.*),.*\)\s*,", line):
                        if not delete_debug:
                            line = "% " + line
                            tmp_content.append(line)
                        match = re.match(r".*time_call\((.*),.*\)\s*,", line)
                        predicate = match.group(1)
                        print(f"Extracted predicate from time_call: {predicate}")
                        tmp_content.append(f"{predicate},\n")
                    elif re.match(r".*time_call\((.*),.*\)\.", line):
                        if not delete_debug:
                            line = "% " + line
                            tmp_content.append(line)
                        match = re.match(r".*time_call\((.*),.*\)\s*\.", line)
                        predicate = match.group(1)
                        print(f"Extracted predicate from time_call: {predicate}")
                        tmp_content.append(f"{predicate}.\n")
                    else:
                        tmp_content.append(line)


            # Graph visualization debugging statements
            elif re.match(r".*graph_emit.*\(.*\)\s*:-", line):
                tmp_content.append(line)
            elif re.match(r".*graph_emit.*\(.*\)\s*,", line):
                if debug_viz:
                    tmp_content.append(line)
                else:
                    if not delete_debug:
                        line = "% " + line
                        tmp_content.append(line)
            elif re.match(r".*graph_emit.*\(.*\)\s*\.", line):
                if debug_viz:
                    tmp_content.append(line)
                else:
                    if not delete_debug:
                        line = "% " + line
                        tmp_content.append(line)
                    tmp_content.append("true.\n")

            elif re.match(r".*graph_reset_state_ids\s*:-", line):
                tmp_content.append(line)
            elif re.match(r".*graph_reset_state_ids\s*,", line):
                if debug_viz:
                    tmp_content.append(line)
                else:
                    if not delete_debug:
                        line = "% " + line
                        tmp_content.append(line)
            elif re.match(r".*graph_reset_state_ids\s*.", line):
                if debug_viz:
                    tmp_content.append(line)
                else:
                    if not delete_debug:
                        line = "% " + line
                        tmp_content.append(line)
                    tmp_content.append("true.\n")

            # Otherwise just add the line as is
            else:
                tmp_content.append(line)

    return "".join(tmp_content)


def init_directory(tmp_dir: Path, force: bool) -> None:
    """
    Initialize the temporary directory for Prolog files.

    Parameters
    ----------
    tmp_dir : Path
        Temporary directory used for generated intermediate files.
    force : bool
        Flag controlling whether force behavior is enabled.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    # If the folder exists, ask if it should be removed and recreated, if force is passed, then execute directly
    if tmp_dir.exists():
        print(f"Temporary directory {tmp_dir} already exists.")
        if force or input(f"Directory {tmp_dir} exists. Remove and recreate? (y/n) ") == "y":
            print(f"Removing and recreating temporary directory {tmp_dir}.")
            for item in tmp_dir.glob("*"):
                if item.is_dir():
                    item.rmdir()
                else:
                    item.unlink()
        else:
            print("Aborting.")
            exit(1)

    # Create temporary directory for Prolog files
    tmp_dir.mkdir(exist_ok=True)


def execute_prolog_file(tmp_dir: Path, no_exec: bool, debug_timings: bool, debug_viz: bool) -> None:
    """
    Execute the Prolog file using SWI-Prolog.

    Parameters
    ----------
    tmp_dir : Path
        Temporary directory used for generated intermediate files.
    no_exec : bool
        Flag controlling whether no exec behavior is enabled.
    debug_timings : bool
        Flag controlling whether debug timings behavior is enabled.
    debug_viz : bool
        Flag controlling whether debug viz behavior is enabled.

    Returns
    -------
    None
        This function performs side effects and returns nothing.
    """
    if not no_exec:
        # Compose runtime debug toggles as Prolog goals.
        goals = []
        if debug_timings:
            goals.append("enable_time_debug")
        if debug_viz:
            goals.append("enable_graph_debug")
        goals.append("plan")
        command = ["swipl", "--stack_limit=10G", "-s", f"{tmp_dir}/planner.pl", "-t", f"{', '.join(goals)}."]
    else:
        # In no-exec mode, we still validate that SWI can load planner.pl cleanly.
        command = ["swipl", "--stack_limit=10G", "-s", f"{tmp_dir}/planner.pl", "-t", "halt."]

    # Execute the command showing the output in real time
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while executing the Prolog file: {e}")



def main2(args):
    # Initialize temporary directory
    """
    Run the alternate execution flow that merges included Prolog files first.

    Parameters
    ----------
    args : Any
        Parsed command-line arguments namespace.

    Returns
    -------
    Any
        Result returned by `main2`.
    """
    init_directory(args.tmp_path, args.force)

    # Merge the content of all the Prolog files into a single planner.pl file
    lines = []
    replace_include_with_content(Path(args.prolog_file), lines)
    content = parse_content(lines, args.debug, args.delete_debug, args.debug_timings, args.debug_viz)

    with open(args.tmp_path / "planner.pl", "w") as f:
        f.write(content)

    # Execute the Prolog file
    print(f"Executing Prolog file {args.tmp_path / 'planner.pl'}.")
    execute_prolog_file(args.tmp_path, args.no_exec, args.debug_timings, args.debug_viz)



def main(args):
    # Initialize temporary directory
    """
    Run the command-line entry point.

    Parameters
    ----------
    args : Any
        Parsed command-line arguments namespace.

    Returns
    -------
    Any
        Result returned by `main`.
    """
    tmp_dir = args.tmp_path
    init_directory(tmp_dir, args.force)

    # Copy all the files from src to the tmp directory
    print(f"Copying Prolog files from src to {tmp_dir}.")
    for file in Path("src").glob("**/*.pl"):
        target = tmp_dir / file.name
        target.write_text(file.read_text())

    # Parse all the files in the temporary directory
    print(f"Parsing Prolog files in {tmp_dir}.")
    for file in tmp_dir.glob("**/*.pl"):
        content = parse_content(file.read_text(), args.debug, args.delete_debug, args.debug_timings, args.debug_viz)
        file.write_text(content)

    # Execute the Prolog file
    print(f"Executing Prolog file {tmp_dir / 'planner.pl'}.")
    execute_prolog_file(tmp_dir, args.no_exec, args.debug_timings, args.debug_viz)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute a Prolog file with SWI-Prolog.")
    parser.add_argument("prolog_file", help="Path to the Prolog file to execute", type=Path)
    # Storing temporary files options
    parser.add_argument("--tmp-path", help="Path to temporary directory", type=Path, default=Path("tmp"))
    parser.add_argument("--force", help="Force execution without confirmation", action="store_true")
    parser.add_argument("--no-unify", help="Copy the content of the ensure_loaded files instead of merging them into one file", action="store_true")
    # Execution options 
    parser.add_argument("--simple", help="Use simple execution mode (directly calls the Prolog file without pre-processing).", action="store_true")
    parser.add_argument("--no-exec", help="Do not execute the Prolog file", action="store_true")
    # Debug options
    parser.add_argument("--debug", help="Enable debug mode", action="store_true")
    parser.add_argument("--debug-timings", help="Enable timing debug output (time_emit/time_call).", action="store_true")
    parser.add_argument("--debug-viz", "--debug-graph", dest="debug_viz", help="Enable graph visualization debug output (graph_emit).", action="store_true")
    parser.add_argument("--delete-debug", help="Delete debug statements instead of commenting debug mode. Can be enabled only if --debug is set", action="store_true")
    args = parser.parse_args()

    print(args)

    if args.simple:
        # Simple mode bypasses preprocessing and executes the selected file directly.
        goals = []
        if args.debug:
            goals.append("enable_debug")
        else:
            goals.append("disable_debug")

        if args.debug_timings:
            goals.append("enable_time_debug")
        if args.debug_viz:
            goals.append("enable_graph_debug")
        goals.append("plan")
        command = ["swipl", "--stack_limit=10G", "-s", f"{args.prolog_file}", "-t", f"{', '.join(goals)}."]
        
        print("Executing Prolog file in simple mode.")
        print(f"Command: {' '.join(command)}")
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            print(f"An error occurred while executing the Prolog file: {e}")

    else:
        if args.no_unify:
            main(args)
        else:
            main2(args)

        print("Finished processing Prolog files.")

# If the SWIPL shell was quit unexpectedly, then the carriage return may be messed up. Reset it with `stty icrnl` or with `stty sane` or `reset`.
