:- ensure_loaded('../src/consistency_checks.pl').

:- dynamic consistency_checks_test_dir/1.

:- prolog_load_context(directory, TestDir),
   asserta(consistency_checks_test_dir(TestDir)).

consistency_fixture(Name, Path) :-
    consistency_checks_test_dir(TestDir),
    atomic_list_concat([TestDir, '/fixtures/', Name], Path).

test_durative_lifecycle_consistency :-
    consistency_fixture('consistency_lifecycle_bad.pl', BadKB),
    with_checked_kb_file(BadKB, findall(Issue, durative_lifecycle_issue_for(hl, Issue), Issues)),
    member(issue(move_block(_Agent, Block, _From, _To), start_effect_conflicts_with_lifecycle_condition(del(clear(Block)), clear(Block))), Issues),
    member(issue(pick_up(_Robot, _Gripper, Ball, Room), start_effect_conflicts_with_lifecycle_condition(del(at_ball(Ball, Room)), at_ball(Ball, Room))), Issues),
    \+ start_effect_violates_end_precondition(del(clear(block1)), clear(block2)),
    start_effect_violates_end_precondition(del(clear(Block)), clear(Block)),
    succ_msg('OK\n').

test_durative_lifecycle_consistency :-
    fail_msg('FAIL\n'),
    fail.

test_effects_no_opposites_respects_disequality :-
    consistency_fixture('consistency_effects_disequality_ok.pl', GoodKB),
    with_checked_kb_file(GoodKB, effects_no_opposites_for(hl)),
    \+ same_phase_effects_conflict(clear(Block1), clear(Block2), [Block1 \= Block2]),
    same_phase_effects_conflict(clear(Block), clear(Block), []),
    succ_msg('OK\n').

test_effects_no_opposites_respects_disequality :-
    fail_msg('FAIL\n'),
    fail.

run_all_consistency_checks_tests :-
    info_msg('RUNNING TEST FOR CONSISTENCY CHECKS... \n'), !,
    format('    Testing durative lifecycle consistency... '), !,
    test_durative_lifecycle_consistency,
    format('    Testing effect opposites with disequality... '), !,
    test_effects_no_opposites_respects_disequality.
