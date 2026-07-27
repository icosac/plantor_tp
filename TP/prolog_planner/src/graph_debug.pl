%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%                       GRAPH DEBUGGING HELPERS                              %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

:- dynamic graph_debug/1.
:- dynamic graph_state_id/2.
:- dynamic graph_state_counter/1.
graph_debug(false).
graph_state_counter(0).

enable_graph_debug  :- retractall(graph_debug(_)), assertz(graph_debug(true)).
disable_graph_debug :- retractall(graph_debug(_)), assertz(graph_debug(false)).

graph_emit(Format, Args) :-
    graph_debug(true)
    -> format(Format, Args)
    ;  true.

graph_reset_state_ids :-
    retractall(graph_state_id(_, _)),
    retractall(graph_state_counter(_)),
    assertz(graph_state_counter(0)).

graph_state_key(State, Key) :-
    % Canonicalize list order to match equal_lists/2 semantics.
    msort(State, Sorted),
    ( graph_state_id(Sorted, Existing)
      -> Key = Existing
      ;  graph_state_counter(Counter),
         Key = Counter,
         Next is Counter + 1,
         retractall(graph_state_counter(_)),
         assertz(graph_state_counter(Next)),
         assertz(graph_state_id(Sorted, Key))
    ).

graph_emit_state(State) :-
    graph_state_key(State, Key),
    graph_emit('GRAPH STATE ~w ~w\n', [Key, State]).

graph_emit_init(State) :-
    graph_state_key(State, Key),
    graph_emit('GRAPH INIT ~w\n', [Key]),
    graph_emit_state(State).

graph_emit_goal(State) :-
    graph_state_key(State, Key),
    graph_emit('GRAPH GOAL ~w\n', [Key]),
    graph_emit_state(State).

graph_emit_goal_reached(State, Cost, Depth) :-
    graph_state_key(State, Key),
    graph_emit('GRAPH GOAL_REACHED ~w ~w ~w\n', [Key, Depth, Cost]),
    graph_emit_state(State).

graph_emit_pop(State, Depth, Cost) :-
    graph_state_key(State, Key),
    graph_emit('GRAPH POP ~w ~w ~w\n', [Key, Depth, Cost]),
    graph_emit_state(State).

graph_emit_skip(State, Reason, Depth) :-
    graph_state_key(State, Key),
    graph_emit('GRAPH SKIP ~w ~w ~w\n', [Key, Reason, Depth]),
    graph_emit_state(State).

% Data is a list containing: ActionName, PreconditionsStart, PreconditionsEnd, Overall, 
% EffectsStart, EffectsEnd, Duration and it's empty when the edge is of type skipped_close or 
% skipped_open_better
graph_emit_edge(FromState, ToState, StepLabel, Outcome, NewDepth, NewCost, Data) :-
    graph_state_key(FromState, FromKey),
    graph_state_key(ToState, ToKey),
    graph_emit('GRAPH EDGE ~w ~w ~w ~w ~w ~w ~w\n',
               [FromKey, ToKey, StepLabel, Outcome, NewDepth, NewCost, Data]),
    graph_emit_state(FromState),
    graph_emit_state(ToState).

