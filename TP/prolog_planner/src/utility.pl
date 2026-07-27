%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%                             UTILITY FUNCTIONS                              %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

:- dynamic planner_debug/1.
planner_debug(false).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% :brief: Change planner_debug(X) to set the debug mode on or off. 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
enable_debug  :- retractall(planner_debug(_)), assert(planner_debug(true)).
disable_debug :- retractall(planner_debug(_)), assert(planner_debug(false)).
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% :brief: prints the message with the format provided if the predicate 
% planner_debug(true) is set.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
debug_format(Format) :- 
	planner_debug(true) -> format(Format); true.

debug_format(Format, Args) :- 
	planner_debug(true) -> format(Format, Args); true.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

succ_msg(Msg, Args) :-
    format('\e[1;32m'),
    format(Msg, Args),
    format('\e[0m').
succ_msg(Msg) :-
    format('\e[1;32m~w\e[0m', [Msg]).

info_msg(Msg, Args) :-
    format('\e[1;34m'),
    format(Msg, Args),
    format('\e[0m').
info_msg(Msg) :-
    format('\e[1;34m~w\e[0m', [Msg]).

fail_msg(Msg, Args) :-
    format('\e[1;31m'),
    format(Msg, Args),
    format('\e[0m').
fail_msg(Msg) :-
    format('\e[1;31m~w\e[0m', [Msg]).

fatal_msg(Msg, Args) :-
    fail_msg(Msg, Args), 
    halt(1).
fatal_msg(Msg) :-
    fail_msg(Msg), 
    halt(1).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* Converts a list to a set, removing duplicates.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
set_from_list(List, Set) :-
    set_from_list(List, [], Set).
set_from_list([], Set, Set).
set_from_list([H|T], Set, RetSet) :-
    (
        \+member(H, Set)
        ->(
            append(Set, [H], TmpSet),
            set_from_list(T, TmpSet, RetSet)
        );(
            set_from_list(T, Set, RetSet)
        )
    ).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* Checks that two sets contain the same elements, regardless of order.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
equal_sets(Set1, Set2) :-
    length(Set1, L), 
    length(Set2, L),
    equal_sets_inner(Set1, Set2).
equal_sets_inner([], _).
equal_sets_inner([H|T], Set2) :-
    member(H, Set2),
    equal_sets_inner(T, Set2).
equal_sets_inner(_, _) :- fail.


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* Removes one occurrence of an element from a list.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
remove_one_element_from_list(Elem, List, NewList) :-
    remove_one_element_from_list(Elem, List, [], NewList).
remove_one_element_from_list(Elem, [Elem|T], Rest, NewList) :-
    append(Rest, T, NewList).
remove_one_element_from_list(_Elem, [], Ret, Ret).
remove_one_element_from_list(Elem, [H|T], Rest, Ret) :-
    Elem \= H,
    remove_one_element_from_list(Elem, T, [H|Rest], Ret).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* Checks that two lists contain the same elements, regardless of order.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
equal_lists(List1, List2) :-
    length(List1, L), 
    length(List2, L),
    equal_lists_inner(List1, List2).
equal_lists_inner([], []).
equal_lists_inner(List1, List2) :-
    List1 = [H1|T1],
    member(H1, List2),
    remove_one_element_from_list(H1, List2, NewList2),
    equal_lists_inner(T1, NewList2).
equal_lists_inner(_, _) :- fail.


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* Prints a list of elements. If they are edges, hl_actions, hl_d_actions, or entries, it uses the correct function to print them.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

print_list(L) :-
    print_list(L, false).

print_list([], _).
print_list([H|T], ForcePrint) :-
    print_edge(H, ForcePrint),
    print_list(T, ForcePrint).
print_list([H|T], ForcePrint) :-
    print_hl_action(H, ForcePrint),
    print_list(T, ForcePrint).
print_list([H|T], ForcePrint) :-
    print_hl_d_action(H, ForcePrint),
    print_list(T, ForcePrint).
print_list([H|T], ForcePrint) :-
    (
        ForcePrint == true
        -> format('\t~w~n', [H])
        ; 
        debug_format('\t~w~n', [H])
    ),
    print_list(T, ForcePrint).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%!- Prints a hl_action
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
print_hl_action(hl_action(Name, Preconditions, Groundings, Effects)) :-
print_hl_action(hl_action(Name, Preconditions, Groundings, Effects), false).
print_hl_action(hl_action(Name, Preconditions, Groundings, Effects), ForcePrint) :-
    ForcePrint == true
    -> format('hl_action(~w\n\t~w\n\t~w\n\t~w).\n', [Name, Preconditions, Groundings, Effects])
    ;  
    debug_format('hl_action(~w\n\t~w\n\t~w\n\t~w).\n', [Name, Preconditions, Groundings, Effects]).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%!- Prints a hl_d_action
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
print_hl_d_action(hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, Groundings, EffectsStart, EffectsEnd, Duration)) :-
print_hl_d_action(hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, Groundings, EffectsStart, EffectsEnd, Duration), false).
print_hl_d_action(hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, Groundings, EffectsStart, EffectsEnd, Duration), ForcePrint) :-
    ForcePrint == true
    -> format('hl_d_action(\n\tName: ~w\n\tPreconditionsStart: ~w\n\tPreconditionsEnd: ~w\n\tOverall: ~w\n\tGroundings: ~w\n\tEffectsStart: ~w\n\tEffectsEnd: ~w\n\tDuration: ~w\n).\n', [Name, PreconditionsStart, PreconditionsEnd, Overall, Groundings, EffectsStart, EffectsEnd, Duration])
    ;  
    debug_format('hl_d_action(\n\tName: ~w\n\tPreconditionsStart: ~w\n\tPreconditionsEnd: ~w\n\tOverall: ~w\n\tGroundings: ~w\n\tEffectsStart: ~w\n\tEffectsEnd: ~w\n\tDuration: ~w\n).\n', [Name, PreconditionsStart, PreconditionsEnd, Overall, Groundings, EffectsStart, EffectsEnd, Duration]).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%!- Prints a state
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
print_state(entry(State, PrevState, Transition, [ActionName, EffectsEnd], Time, Depth)) :-
print_state(entry(State, PrevState, Transition, [ActionName, EffectsEnd], Time, Depth), false).
print_state(entry(State, PrevState, Transition, [ActionName, EffectsEnd], Time, Depth), ForcePrint) :-
    ForcePrint == true
    -> format('entry(\n\tState: ~w\n\tPrevState: ~w\n\tTransition: ~w\n\tActionName: ~w\n\tEffectsEnd ~w\n\tTime: ~w\n\tCost: ~w\n).\n', [State, PrevState, Transition, ActionName, EffectsEnd, Time, Depth])
    ;
    debug_format('entry(\n\tState: ~w\n\tPrevState: ~w\n\tTransition: ~w\n\tActionName: ~w\n\tEffectsEnd ~w\n\tTime: ~w\n\tCost: ~w\n).\n', [State, PrevState, Transition, ActionName, EffectsEnd, Time, Depth]).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%!- Prints a node
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
print_node(node(State, PrevState, Cost, Depth)) :-
    print_node(node(State, PrevState, Cost, Depth), false).
print_node(node(State, PrevState, Cost, Depth), ForcePrint) :-
    ForcePrint == true
    -> format('node(\n\tState: ~w\n\tPrevState: ~w\n\tCost: ~w\n\tDepth: ~w\n).\n', [State, PrevState, Cost, Depth])
    ;  
    debug_format('node(\n\tState: ~w\n\tPrevState: ~w\n\tCost: ~w\n\tDepth: ~w\n).\n', [State, PrevState, Cost, Depth]).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%!- Prints an edge
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
print_edge(edge(State, PrevState, Transition, Cost)) :-
    print_edge(edge(State, PrevState, Transition, Cost), false).
print_edge(edge(State, PrevState, Transition, Cost), ForcePrint) :-
    ForcePrint == true
    -> format('\tState: ~w\n \tPrevState: ~w\n \tTransition: ~w\n \tCost: ~w\n', [State, PrevState, Transition, Cost])
    ;  
    debug_format('\tState: ~w\n \tPrevState: ~w\n \tTransition: ~w\n \tCost: ~w\n', [State, PrevState, Transition, Cost]).
