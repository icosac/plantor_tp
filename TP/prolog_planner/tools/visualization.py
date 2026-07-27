"""
Build static graph and timing visualizations from planner debug output.
"""

import re
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import textwrap

import argparse


def parse_state(state_str):
    """
    Parse a state string and return a cleaned version.

    Parameters
    ----------
    state_str : Any
        State string extracted from planner logs.

    Returns
    -------
    Any
        Result returned by `parse_state`.
    """
    # Remove the square brackets
    state_str = state_str.strip('[]')
    return state_str


def parse_edges(file_content):
    """
    Parse all edges from the file content.

    Parameters
    ----------
    file_content : Any
        Raw file content read from planner logs or traces.

    Returns
    -------
    Any
        Result returned by `parse_edges`.
    """
    edges = []
    
    # Pattern to match edge additions
    edge_pattern = r'\[add_edge\] Adding edge from \[(.*?)\] to \[(.*?)\]'
    
    for match in re.finditer(edge_pattern, file_content):
        from_state = parse_state(match.group(1))
        to_state = parse_state(match.group(2))
        edges.append((from_state, to_state))
    
    return edges


def parse_transitions(file_content):
    """
    Parse state transitions with their action names.

    Parameters
    ----------
    file_content : Any
        Raw file content read from planner logs or traces.

    Returns
    -------
    Any
        Result returned by `parse_transitions`.
    """
    transitions = {}
    
    # Pattern to match state entries with transitions
    entry_pattern = r'PrevState:\s*\[(.*?)\]\s*State:\s*\[(.*?)\]\s*Transition:\s*(.*?)\s*Cost:'
    
    for match in re.finditer(entry_pattern, file_content, re.DOTALL):
        prev_state = parse_state(match.group(1))
        curr_state = parse_state(match.group(2))
        transition = match.group(3).strip()
        
        if prev_state and curr_state:  # Skip empty prev_state (initial state)
            transitions[(prev_state, curr_state)] = transition
    
    return transitions


def wrap_text(text, width=30):
    """
    Wrap text for better display in nodes.

    Parameters
    ----------
    text : Any
        Input text to parse, search, or transform.
    width : Any, optional
        Maximum line width used when wrapping long text labels.

    Returns
    -------
    Any
        Result returned by `wrap_text`.
    """
    # Split by comma and wrap each predicate
    predicates = text.split(',')
    wrapped_predicates = []
    
    for pred in predicates:
        pred = pred.strip()
        if len(pred) > width:
            # For long predicates, just break at width
            wrapped = textwrap.fill(pred, width=width)
            wrapped_predicates.append(wrapped)
        else:
            wrapped_predicates.append(pred)
    
    # Join with newlines, but limit total lines
    result = '\n'.join(wrapped_predicates[:5])  # Show max 5 predicates
    if len(predicates) > 5:
        result += f'\n... (+{len(predicates)-5} more)'
    
    return result


def create_graph_visualization(edges, transitions, output_file='search_graph.png'):
    """
    Create a visualization of the search graph.

    Parameters
    ----------
    edges : Any
        Collection of graph edges.
    transitions : Any
        Mapping of graph edges to transition/action labels.
    output_file : Any, optional
        Path to the output file used by this operation.

    Returns
    -------
    Any
        Result returned by `create_graph_visualization`.
    """
    # Create a directed graph
    G = nx.DiGraph()
    
    # Add edges
    for edge in edges:
        G.add_edge(edge[0], edge[1])
    
    # Create figure
    plt.figure(figsize=(20, 16))
    
    # Use hierarchical layout
    pos = nx.nx_agraph.graphviz_layout(G, prog='dot', args='-Grankdir=TB')
    
    # Draw nodes with wrapped labels
    node_labels = {node: wrap_text(node) for node in G.nodes()}
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_color='lightblue', 
                          node_size=8000, node_shape='o')
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, edge_color='gray', 
                          arrows=True, arrowsize=20, arrowstyle='->')
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, node_labels, font_size=8, 
                           font_family='monospace')
    
    # Add edge labels (transitions)
    edge_labels = {}
    for edge in G.edges():
        if edge in transitions:
            # Shorten transition names for display
            trans = transitions[edge]
            if trans.startswith('move_arm_start'):
                trans = trans.replace('move_arm_start', 'move')
            elif trans.startswith('change_tool_start'):
                trans = trans.replace('change_tool_start', 'change_tool')
            edge_labels[edge] = trans
    
    nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=7, 
                                font_color='red', font_family='monospace')
    
    # Find initial and goal states
    initial_nodes = [node for node in G.nodes() if G.in_degree(node) == 0]
    goal_nodes = [node for node in G.nodes() if G.out_degree(node) == 0]
    
    # Highlight initial and goal states
    if initial_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=initial_nodes, 
                              node_color='lightgreen', node_size=8000)
    if goal_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=goal_nodes, 
                              node_color='lightcoral', node_size=8000)
    
    plt.title('Breadth-First Search Graph\n(Green: Initial State, Red: Goal State)', 
              fontsize=16, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Graph saved to {output_file}")
    print(f"Total nodes: {G.number_of_nodes()}")
    print(f"Total edges: {G.number_of_edges()}")
    print(f"Initial states: {len(initial_nodes)}")
    print(f"Goal states: {len(goal_nodes)}")


def create_simplified_graph(edges, transitions, output_file='search_graph_simplified.png'):
    """
    Create a simplified visualization with abbreviated state names.

    Parameters
    ----------
    edges : Any
        Collection of graph edges.
    transitions : Any
        Mapping of graph edges to transition/action labels.
    output_file : Any, optional
        Path to the output file used by this operation.

    Returns
    -------
    Any
        Result returned by `create_simplified_graph`.
    """
    # Create a directed graph
    G = nx.DiGraph()
    
    # Create abbreviated node names
    node_mapping = {}
    for i, node in enumerate(set([e[0] for e in edges] + [e[1] for e in edges])):
        node_mapping[node] = f"S{i}"
    
    # Add edges with abbreviated names
    for edge in edges:
        G.add_edge(node_mapping[edge[0]], node_mapping[edge[1]])
    
    # Create figure
    plt.figure(figsize=(12, 10))
    
    # Use hierarchical layout
    pos = nx.nx_agraph.graphviz_layout(G, prog='dot', args='-Grankdir=TB')
    
    # Draw the graph
    nx.draw(G, pos, with_labels=True, node_color='lightblue', 
            node_size=3000, font_size=12, font_weight='bold',
            arrows=True, arrowsize=20, edge_color='gray')
    
    # Find initial and goal states
    original_initial = [node for node, abbrev in node_mapping.items() 
                       if sum(1 for e in edges if e[1] == node) == 0]
    original_goal = [node for node, abbrev in node_mapping.items() 
                    if sum(1 for e in edges if e[0] == node) == 0 and 
                    any(e[1] == node for e in edges)]
    
    initial_nodes = [node_mapping[n] for n in original_initial if n in node_mapping]
    goal_nodes = [node_mapping[n] for n in original_goal if n in node_mapping]
    
    # Highlight initial and goal states
    if initial_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=initial_nodes, 
                              node_color='lightgreen', node_size=3000)
    if goal_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=goal_nodes, 
                              node_color='lightcoral', node_size=3000)
    
    plt.title('Simplified Search Graph\n(Green: Initial, Red: Goal)', 
              fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\nSimplified graph saved to {output_file}")
    
    # Save mapping to file
    with open('state_mapping.txt', 'w') as f:
        f.write("State Abbreviation Mapping:\n")
        f.write("=" * 80 + "\n\n")
        for state, abbrev in sorted(node_mapping.items(), key=lambda x: int(x[1][1:])):
            f.write(f"{abbrev}:\n{state}\n\n")
    
    print("State mapping saved to state_mapping.txt")


def graph_viz(file_path):
    # Read the input file
    """
    Handle graph viz.

    Parameters
    ----------
    file_path : Any
        Path to the file being read or transformed.

    Returns
    -------
    Any
        Result returned by `graph_viz`.
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Parse edges and transitions
    edges = parse_edges(content)
    transitions = parse_transitions(content)
    
    print(f"Found {len(edges)} edges")
    print(f"Found {len(transitions)} transitions")
    
    if edges:
        # Create detailed graph
        create_graph_visualization(edges, transitions, 'search_graph_detailed.png')
        
        # Create simplified graph
        create_simplified_graph(edges, transitions, 'search_graph_simplified.png')
        
        # Extract and visualize the solution path if found
        solution_pattern = r'Plan:\s*(.*?)Plan took time'
        solution_match = re.search(solution_pattern, content, re.DOTALL)
        
        if solution_match:
            solution_steps = solution_match.group(1).strip().split('\n')
            solution_steps = [step.strip() for step in solution_steps if step.strip()]
            
            print("\nSolution path found:")
            for i, step in enumerate(solution_steps, 1):
                print(f"  {i}. {step}")
            
            # You could create a separate visualization for just the solution path
            # by filtering edges that correspond to the solution steps
    else:
        print("No edges found in the input file!")



def parse_timing_info(content):
    """
    Parse timing info.

    Parameters
    ----------
    content : Any
        Full text content being parsed or transformed.

    Returns
    -------
    Any
        Result returned by `parse_timing_info`.
    """
    import re
    import numpy as np
    timing_info = {}
    current_depth = 0
    for line in content.splitlines():
        # Group timing measurements under the most recently reported search depth.
        match = re.search(r'\[.*\] Exploring depth: (?P<depth>\d+)', line)
        if match and match['depth'] not in timing_info:
            timing_info[match['depth']] = {}
            current_depth = match['depth']

        else:
            match = re.search(r'\[.*\] Time taken for (?P<time_name>.*) time{cpu:(?P<time>\d+\.*\d*e*[-\+]*\d*),', line)
            if match:
                time_name = match['time_name'].strip()
                time_value = float(match['time'])

                if current_depth not in timing_info:
                    timing_info[current_depth] = {}
                if time_name not in timing_info[current_depth]:
                    timing_info[current_depth][time_name] = []

                timing_info[current_depth][time_name].append(time_value)

    ret_val = {}
    for depth, times in timing_info.items():
        for time_name, values in times.items():
            if time_name+"_avg" not in ret_val:
                ret_val[time_name+"_avg"] = {}
                ret_val[time_name+"_sum"] = {}
            ret_val[time_name+"_avg"][depth] = np.mean(values)
            ret_val[time_name+"_sum"][depth] = np.sum(values)

    return ret_val


def create_time_visualization(timing_info, img_path):
    """
    Create time visualization.

    Parameters
    ----------
    timing_info : Any
        Aggregated timing metrics keyed by depth and metric name.
    img_path : Any
        Path where the generated image is saved.

    Returns
    -------
    Any
        Result returned by `create_time_visualization`.
    """
    import matplotlib.pyplot as plt

    # Prepare data for plotting
    fig, ax = plt.subplots(figsize=(10, 6))

    for time_name, depths in timing_info.items():
        # Plot one line per timing metric (avg/sum per depth).
        depth_labels = sorted(depths.keys())
        values = [depths[depth] for depth in depth_labels]
        ax.plot(depth_labels, values, marker='o', label=time_name)

    ax.set_xlabel("Search Depth")
    ax.set_ylabel("Time (seconds)")
    ax.set_title("Search Times by Depth")
    ax.legend()
    plt.grid()
    plt.savefig(img_path, dpi=300, bbox_inches='tight')
    plt.close()


def time_viz(file_path):
    # Read the input file
    """
    Handle time viz.

    Parameters
    ----------
    file_path : Any
        Path to the file being read or transformed.

    Returns
    -------
    Any
        Result returned by `time_viz`.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    # Parse timing information
    timing_info = parse_timing_info(content)

    if timing_info:
        print(f"Found {len(timing_info)} timing entries")
        print(timing_info)
        # Create a time visualization
        create_time_visualization(timing_info, 'search_times.png')
    else:
        print("No timing information found in the input file!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize Prolog search graph or times.")
    parser.add_argument("--graph", help="Create a graph visualization of the search", action="store_true")
    parser.add_argument("--times", help="Create a visualization of the search times", action="store_true")
    parser.add_argument("input", help="Input file containing search data", default="tmp.txt")

    args = parser.parse_args()
    if args.graph:
        graph_viz(args.input)
    if args.times:
        time_viz(args.input)
