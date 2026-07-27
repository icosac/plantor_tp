%%% The way a comment starts before a functions tells:
%%% - %* There is a working test
%%% - %? There is a test, but it's not finished yet 
%%% - %! There is no test
%%% - %!- There is no test and there will probably never be one.

:- ensure_loaded('src/kb.pl').
:- ensure_loaded('src/utility.pl').
:- ensure_loaded('src/applicability.pl').
:- ensure_loaded('src/generate.pl').
:- ensure_loaded('src/bfs_planner.pl').
:- ensure_loaded('src/plan_extraction.pl').

:- ensure_loaded('src/mappings.pl').

emit_profile(Label, Time) :-
    format('[profile] prolog.~w ~w~n', [Label, Time]).


to_plan :- total_order_plan.
total_order_plan :-
    % enable_debug,
    call_time(bfs_planner(10, Plan), TimePlan),
    emit_profile(total_order_planning, TimePlan),
    format('Plan:\n'), 
    print_list(Plan, true),
    format('Plan took ~w seconds\n', [TimePlan]),
    true.


ll_plan :- low_level_plan.
low_level_plan :-
    call_time(bfs_planner(10, HL_Plan), TimePlan),
    emit_profile(total_order_planning, TimePlan),
    format('High Level Plan:\n'), 
    print_list(HL_Plan, true),
    init_state(Init),
    ll_init(LL_Init),
    append(Init, LL_Init, Full_Init),
    format('[low_level_plan] Initial Low Level State: ~w\n', [Full_Init]),
    call_time(apply_mappings(Full_Init, HL_Plan, LL_Plan), TimeMapping),
    emit_profile(low_level_mapping, TimeMapping),
    format('Low Level Plan:\n'),
    print_list(LL_Plan, true),
    true.


partial_order_plan :-
    call_time(bfs_planner(10, Plan), TimePlan),
    emit_profile(total_order_planning, TimePlan),
    call_time(partial_order_plan(Plan, POPlan), TimePartialOrder),
    emit_profile(partial_order_construction, TimePartialOrder),
    format('Partial Order Plan:\n'), 
    print_list(POPlan, true),
    true.
