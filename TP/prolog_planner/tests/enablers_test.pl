:- ensure_loaded('../src/enablers.pl').

:- dynamic failed_enablers/1.
:- dynamic hl_d_action/7.
:- dynamic ll_d_action/7.

failed_enablers(false).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

reset_enabler_test_actions :-
    retractall(hl_d_action(_, _, _, _, _, _, _)),
    retractall(ll_d_action(_, _, _, _, _, _, _)).

setup_nested_mapping_actions :-
    reset_enabler_test_actions,
    assertz(hl_d_action(hl_a1, [], [], [], [], [], [1, 10])),
    assertz(hl_d_action(hl_a2, [], [], [], [], [], [1, 10])),
    assertz(ll_d_action(ll_a1, [], [], [], [], [], [1, 1])),
    assertz(ll_d_action(ll_a2, [], [], [], [], [], [1, 1])),
    assertz(ll_d_action(ll_a3, [], [], [], [], [], [1, 1])),
    assertz(ll_d_action(ll_a4, [], [], [], [], [], [1, 1])).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

test_nested_hl_intervals_do_not_steal_inner_ll_steps :-
    setup_nested_mapping_actions,
    Plan = [
        0-start(hl_a1),
        1-start(ll_a1),
        2-end(ll_a1),
        3-start(ll_a2),
        4-end(ll_a2),
        5-start(hl_a2),
        6-start(ll_a3),
        7-end(ll_a3),
        8-start(ll_a4),
        9-end(ll_a4),
        10-end(hl_a2),
        11-end(hl_a1)
    ],
    extract_enablers(Plan, Enablers),
    member(enabler(0-start(hl_a1), 1-start(ll_a1), assumption(hl_start_enables_ll)), Enablers),
    member(enabler(0-start(hl_a1), 4-end(ll_a2), assumption(hl_start_enables_ll)), Enablers),
    member(enabler(4-end(ll_a2), 11-end(hl_a1), assumption(ll_enables_hl_end)), Enablers),
    member(enabler(5-start(hl_a2), 6-start(ll_a3), assumption(hl_start_enables_ll)), Enablers),
    member(enabler(9-end(ll_a4), 10-end(hl_a2), assumption(ll_enables_hl_end)), Enablers),
    \+ member(enabler(0-start(hl_a1), 6-start(ll_a3), assumption(hl_start_enables_ll)), Enablers),
    \+ member(enabler(6-start(ll_a3), 11-end(hl_a1), assumption(ll_enables_hl_end)), Enablers),
    \+ member(enabler(4-end(ll_a2), 6-start(ll_a3), assumption(ll_sequence)), Enablers),
    reset_enabler_test_actions,
    succ_msg('OK\n').

test_nested_hl_intervals_do_not_steal_inner_ll_steps :-
    reset_enabler_test_actions,
    retractall(failed_enablers(_)),
    assertz(failed_enablers(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

test_ll_sequence_orders_all_later_steps_in_mapping :-
    setup_nested_mapping_actions,
    Plan = [
        0-start(hl_a1),
        1-start(ll_a1),
        2-end(ll_a1),
        3-start(ll_a2),
        4-end(ll_a2),
        5-start(ll_a3),
        6-end(ll_a3),
        7-start(ll_a4),
        8-end(ll_a4),
        9-end(hl_a1)
    ],
    extract_enablers(Plan, Enablers),
    member(enabler(2-end(ll_a1), 3-start(ll_a2), assumption(ll_sequence)), Enablers),
    member(enabler(2-end(ll_a1), 5-start(ll_a3), assumption(ll_sequence)), Enablers),
    member(enabler(2-end(ll_a1), 7-start(ll_a4), assumption(ll_sequence)), Enablers),
    reset_enabler_test_actions,
    succ_msg('OK\n').

test_ll_sequence_orders_all_later_steps_in_mapping :-
    reset_enabler_test_actions,
    retractall(failed_enablers(_)),
    assertz(failed_enablers(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

test_hl_causal_edges_project_to_ll_boundaries :-
    reset_enabler_test_actions,
    assertz(hl_d_action(hl_a, [], [], [], [], [add(token)], [1, 10])),
    assertz(hl_d_action(hl_b, [token], [], [], [], [], [1, 10])),
    assertz(ll_d_action(ll_a1, [], [], [], [], [], [1, 1])),
    assertz(ll_d_action(ll_b1, [], [], [], [], [], [1, 1])),
    Plan = [
        0-start(hl_a),
        1-start(ll_a1),
        2-end(ll_a1),
        3-end(hl_a),
        4-start(hl_b),
        5-start(ll_b1),
        6-end(ll_b1),
        7-end(hl_b)
    ],
    extract_enablers(Plan, Enablers),
    member(enabler(3-end(hl_a), 4-start(hl_b), causal([token])), Enablers),
    member(enabler(2-end(ll_a1), 5-start(ll_b1), assumption(hl_boundary_projection)), Enablers),
    reset_enabler_test_actions,
    succ_msg('OK\n').

test_hl_causal_edges_project_to_ll_boundaries :-
    reset_enabler_test_actions,
    retractall(failed_enablers(_)),
    assertz(failed_enablers(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

run_all_enablers_tests :-
    info_msg('RUNNING TEST FOR ENABLERS... \n'), !,
    format('    Testing nested HL ownership............ '), !,
    test_nested_hl_intervals_do_not_steal_inner_ll_steps, !,
    format('    Testing LL sequence transitive order... '), !,
    test_ll_sequence_orders_all_later_steps_in_mapping, !,
    format('    Testing HL boundary projection......... '), !,
    test_hl_causal_edges_project_to_ll_boundaries, !,
    failed_enablers(Failed), \+Failed.
