%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%                                BFS PLANNER                                 %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% :-ensure_loaded('../src/kb.pl').
:-ensure_loaded('../src/bfs_planner.pl').
:-ensure_loaded('../src/utility.pl').
:-ensure_loaded('../src/mappings.pl').
:-ensure_loaded('../src/enablers.pl').

emit_profile(Label, Time) :-
  format('[profile] prolog.~w ~w~n', [Label, Time]).


plan :-
  plan(4).

plan(Max_depth) :-
  format('[planner] Starting BFS planner\n'),
  call_time(bfs_planner(Max_depth, Plan), TimePlan),
  emit_profile(total_order_planning, TimePlan),
  (
    Plan \= []
    ->(
      format('[planner] Plan found in ~w\n', [TimePlan]),
      print_list(Plan, true), !,
      init_state(Init),
      call_time(apply_mappings(Init, Plan, LL_Plan), TimeMapping),
      emit_profile(low_level_mapping, TimeMapping),
      format('[planner] LL Plan:'),
      print_list(LL_Plan, true),
      call_time(extract_enablers(LL_Plan, Enablers), TimeEnablers),
      emit_profile(enabler_extraction, TimeEnablers),
      format('[planner] Enablers:'),
      print_list(Enablers, true),
      call_time(extract_start_end_links(LL_Plan, StartEndLinks), TimeStartEndLinks),
      emit_profile(start_end_link_extraction, TimeStartEndLinks),
      format('[planner] Start/end link terms:'),
      print_list(StartEndLinks, true),
      call_time(print_start_end_links(LL_Plan, StartEndLinks), TimeStartEndPrinting),
      emit_profile(start_end_link_printing, TimeStartEndPrinting),
      call_time(print_plan_with_enablers(LL_Plan, Enablers), TimePlanEnablersPrinting),
      emit_profile(plan_with_enablers_printing, TimePlanEnablersPrinting),
      call_time(print_plan_durations(LL_Plan), TimeDurationPrinting),
      emit_profile(duration_constraint_printing, TimeDurationPrinting)
    );(
      format('[planner] No plan found\n')
    )
  ).
