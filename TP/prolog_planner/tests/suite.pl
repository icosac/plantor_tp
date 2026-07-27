:- ensure_loaded('applicability_test.pl').
:- ensure_loaded('utility_test.pl').
:- ensure_loaded('generate_test.pl').
:- ensure_loaded('plan_extraction_test.pl').
:- ensure_loaded('enablers_test.pl').

run_all :-
  disable_debug,
  run_all_utility_tests, !,
  run_all_enablers_tests, !,
  run_all_applicability_tests, !, 
  % run_all_generate_tests, !,
  % run_all_plan_extraction_tests, !,
  true.
