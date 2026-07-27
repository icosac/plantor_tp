%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%                                BFS PLANNER                                 %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% plan(State:entry, StatesToCheck:list(entry), Goal:list, Plan:list, Edges:list(edge))
% node(State:list, PrevState:list, Action:atom, Cost:int, Depth:int, Invariants:list)
% entry(State:list, PrevState:list, TransitionName:atom, [ActionName:atom, PreconditionsEnd:list, EffectsEnd:list], Cost:int, Depth:int)
% edge(State:list, PrevState:list, Transition:atom, Cost:int)

:-ensure_loaded('../src/utility.pl').
:-ensure_loaded('../src/applicability.pl').
:-ensure_loaded('../src/generate.pl').
:-ensure_loaded('../src/graph_debug.pl').
:-ensure_loaded('../src/time_debug.pl').


bfs_planner(MaxDepth, Plan) :-
  validate_max_depth(MaxDepth),
  init_state(InitialState),
  goal_state(GoalState),
  debug_format('[bfs_planner] Starting BFS with MaxDepth ~w\n', [MaxDepth]),
  graph_reset_state_ids,
  graph_emit_init(InitialState),
  graph_emit_goal(GoalState),
  executing_invariants(InitialState, InitialInvariants),
  InitialNode = node(InitialState, [], none, 0, 0, InitialInvariants),
  bfs_search([InitialNode], [], GoalState, [], Plan, MaxDepth).


validate_max_depth(MaxDepth) :-
  integer(MaxDepth),
  MaxDepth >= -1,
  !.
validate_max_depth(MaxDepth) :-
  throw(error(domain_error(max_depth, MaxDepth), bfs_planner/2)).


% max_depth_reached(+MaxDepth, +Depth)
% MaxDepth = -1 is the explicit sentinel for unbounded search.
max_depth_reached(MaxDepth, Depth) :-
  MaxDepth =\= -1,
  Depth >= MaxDepth.


% bfs_search(OPEN, CLOSE, Goal, Plan, Plan, MaxDepth)

bfs_search([], _CLOSE, _Goal, _Plan, [], _MaxDepth) :- 
  debug_format('\n\n[bfs_search0] No more states to explore, returning failure\n').

% This predicate is for when the current state matches the goal state
bfs_search([node(CurrentState, PrevState, Action, Cost, Depth, Invariants)|_TOPEN], CLOSE, Goal, _Plan, RetPlan, _MaxDepth) :-
  graph_emit_pop(CurrentState, Depth, Cost),
  hl_is_state_goal(CurrentState, Goal),
  graph_emit_goal_reached(CurrentState, Cost, Depth),
  debug_format('\n\n[bfs_search1] Current State\n\t~w\nmatches goal state\n\t~w\nwith cost ~w\n', [CurrentState, Goal, Cost]), 
  append(CLOSE, [node(CurrentState, PrevState, Action, Cost, Depth, Invariants)], NewCLOSE),
  reconstruct_plan(node(CurrentState, PrevState, Action, Cost, Depth, Invariants), NewCLOSE, RetPlan).

% This predicate is for when the current state has already been explored
bfs_search([node(CurrentState, _PrevState, _Action, Cost, Depth, _Invariants)|TOPEN], CLOSE, Goal, Plan, RetPlan, MaxDepth) :-
  once(get_state_from_list(CurrentState, CLOSE, _)),
  % member(node(CurrentState, _, _, _, _, _), CLOSE),
  graph_emit_pop(CurrentState, Depth, Cost),
  graph_emit_skip(CurrentState, already_explored, Depth),
  debug_format('\n\n[bfs_search2] State ~w already explored, skipping it\n', [CurrentState]),
  bfs_search(TOPEN, CLOSE, Goal, Plan, RetPlan, MaxDepth).

% This predicate is for when the maximum depth has been reached
bfs_search([node(CurrentState, _PrevState, _Action, Cost, Depth, _Invariants)|TOPEN], CLOSE, Goal, Plan, RetPlan, MaxDepth) :-
  max_depth_reached(MaxDepth, Depth),
  graph_emit_pop(CurrentState, Depth, Cost),
  graph_emit_skip(CurrentState, max_depth, Depth),
  debug_format('\n\n[bfs_search3] Max depth reached: ~w, skipping state ~w\n', [MaxDepth, CurrentState]),
  bfs_search(TOPEN, CLOSE, Goal, Plan, RetPlan, MaxDepth).

% This predicate is for when we need to expand the current state
bfs_search([node(CurrentState, PrevState, Action, Cost, Depth, Invariants)|TOPEN], CLOSE, Goal, Plan, RetPlan, MaxDepth) :-
  graph_emit_pop(CurrentState, Depth, Cost),
  debug_format('\n\n[bfs_search4] Exploring state: ~w\n', [CurrentState]),
  debug_format('[bfs_search4] Exploring depth: ~w\n', [Depth]),
  append(CLOSE, [node(CurrentState, PrevState, Action, Cost, Depth, Invariants)], NewCLOSE),
  applicable_hl_actions(CurrentState, Invariants, ApplicableStartActions, ApplicableEndActions), !,
  (
    (ApplicableStartActions = [], ApplicableEndActions = [])
    ->(
      debug_format('[bfs_search4] No applicable actions found for state: ~w\n', [CurrentState]),
      bfs_search(TOPEN, NewCLOSE, Goal, Plan, RetPlan, MaxDepth)
    );(
      % Apply start actions first
      debug_format('[bfs_search4] Applicable start actions:\n'), 
      print_list(ApplicableStartActions),
      time_call(
        generate_states_start(node(CurrentState, PrevState, Action, Cost, Depth, Invariants), ApplicableStartActions, TOPEN, NewCLOSE, TmpTOPEN),
        TimeGenStatesStart
      ),
      time_emit('[bfs_search4] Time taken for generate_states_start ~w\n', [TimeGenStatesStart]),
      debug_format('[bfs_search4] New OPEN list:\n'),
      print_list(TmpTOPEN),

      % Apply end actions second
      debug_format('[bfs_search4] Applicable end actions:\n'), 
      print_list(ApplicableEndActions),
      time_call(
        generate_states_end(node(CurrentState, PrevState, Action, Cost, Depth, Invariants), ApplicableEndActions, TmpTOPEN, NewCLOSE, NewTOPEN),
        TimeGenStatesEnd
      ),
      time_emit('[bfs_search4] Time taken for generate_states_end ~w\n', [TimeGenStatesEnd]),
      debug_format('[bfs_search4] New OPEN list:\n'),
      print_list(NewTOPEN),
      bfs_search(NewTOPEN, NewCLOSE, Goal, Plan, RetPlan, MaxDepth)
    )
  ).



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%! This predicate reconstructs the plan from the final state by backtracking through the CLOSE list.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
reconstruct_plan(CurrentState, CLOSE, RetPlan) :-
  debug_format('[reconstruct_plan0] Reconstructing plan from state: ~w\n', [CurrentState]),
  debug_format('[reconstruct_plan0] CLOSE list:\n'), 
  print_list(CLOSE),
  reconstruct_plan(CurrentState, CLOSE, [], FinalPlan),
  reverse(FinalPlan, RetPlan).

reconstruct_plan(node(_, [], none, 0, 0, _), _CLOSE, Plan, Plan).
reconstruct_plan(node(_, PrevState, Action, _Cost, _Depth, _), CLOSE, Plan, RetPlan) :-
  debug_format('[reconstruct_plan1] Looking for PrevState: ~w\n', [PrevState]),
  % Find the action that led to the previous state
  get_state_from_list(PrevState, CLOSE, PrevPrevState),
  % Add the action to the plan
  append(Plan, [Action], NewPlan),
  % Continue reconstructing the plan
  debug_format('[reconstruct_plan1] Continuing reconstruction from previous state: ~w\n', [PrevPrevState]),
  reconstruct_plan(PrevPrevState, CLOSE, NewPlan, RetPlan).
