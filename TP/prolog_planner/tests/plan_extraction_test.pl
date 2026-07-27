:- ensure_loaded('../src_old/plan_extraction.pl').

:- dynamic failed_extraction/1.
failed_extraction(false).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% edge(State:list, PrevState:list, Transition:atom, Cost:int)

:- dynamic preamble_extraction_done/1.
preamble_extraction_done(false).
preamble_extraction :-
    preamble_extraction_done(false),
    assertz(edge([pred1],               [],             action1, 1)),
    assertz(edge([pred2],               [],             action2, 2)),
    assertz(edge([pred1, pred2],        [pred1],        action3, 5)),
    assertz(edge([pred3],               [pred1],        action4, 2)),
    assertz(edge([pred2, pred3],        [pred2],        action5, 3)),
    assertz(edge([pred5],               [pred2],        action6, 4)),
    assertz(edge([pred1, pred2, pred3], [pred2, pred3], action7, 5)),
    assertz(edge([pred1, pred2, pred3], [pred3],        action8, 5)),
    assertz(edge([pred1, pred2, pred3], [pred1, pred2], action9, 6)),
    retract(preamble_extraction_done(false)),
    assertz(preamble_extraction_done(true)).
preamble_extraction.


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_find_neighbors :-
    preamble_extraction,
    findall(edge(State, PrevState, Transition, Cost), edge(State, PrevState, Transition, Cost), Edges),
    find_neighbors(
        [pred1],
        Edges,
        [
            edge([pred1], [], action1, 1)
        ]
    ),
    find_neighbors(
        [],
        Edges,
        []
    ),
    find_neighbors(
        [pred1, pred2, pred3],
        Edges,
        [
            edge([pred1, pred2, pred3], [pred2, pred3], action7, 5),
            edge([pred1, pred2, pred3], [pred3],        action8, 5),
            edge([pred1, pred2, pred3], [pred1, pred2], action9, 6)
        ]
    ),
    find_neighbors(
        [pred2],
        Edges,
        [
            edge([pred2], [], action2, 2)
        ]
    ),
    succ_msg('OK\n').
test_find_neighbors :-
    retractall(failed_extraction(_)),
    assertz(failed_extraction(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_sort_neighbors :-
    sort_neighbors(
        [
            edge([pred1], [], action1, 1),
            edge([pred1, pred2, pred3], [pred2, pred3], action7, 5),
            edge([pred2], [], action2, 2),
            edge([pred1, pred2, pred3], [pred1, pred2], action9, 6),
            edge([pred3], [pred1], action4, 2),
            edge([pred1, pred2, pred3], [pred3], action8, 5)
        ],
        [
            edge([pred1], [], action1, 1),
            edge([pred2], [], action2, 2),
            edge([pred3], [pred1], action4, 2),
            edge([pred1, pred2, pred3], [pred2, pred3], action7, 5),
            edge([pred1, pred2, pred3], [pred3], action8, 5),
            edge([pred1, pred2, pred3], [pred1, pred2], action9, 6)
        ]
    ),
    % All costs equal
    sort_neighbors(
        [
            edge([a], [], t1, 2),
            edge([b], [], t2, 2),
            edge([c], [], t3, 2)
        ],
        [
            edge([a], [], t1, 2),
            edge([b], [], t2, 2),
            edge([c], [], t3, 2)
        ]
    ),
    % Already sorted input
    sort_neighbors(
        [
            edge([a], [], t1, 1),
            edge([b], [], t2, 2),
            edge([c], [], t3, 3)
        ],
        [
            edge([a], [], t1, 1),
            edge([b], [], t2, 2),
            edge([c], [], t3, 3)
        ]
    ),
    % Reverse sorted input
    sort_neighbors(
        [
            edge([c], [], t3, 3),
            edge([b], [], t2, 2),
            edge([a], [], t1, 1)
        ],
        [
            edge([a], [], t1, 1),
            edge([b], [], t2, 2),
            edge([c], [], t3, 3)
        ]
    ),
    % Single element
    sort_neighbors(
        [edge([a], [], t1, 1)],
        [edge([a], [], t1, 1)]
    ),
    % Empty list
    sort_neighbors(
        [],
        []
    ),
    % Negative and zero costs
    sort_neighbors(
        [
            edge([a], [], t1, 0),
            edge([b], [], t2, -1),
            edge([c], [], t3, 2)
        ],
        [
            edge([b], [], t2, -1),
            edge([a], [], t1, 0),
            edge([c], [], t3, 2)
        ]
    ),
    succ_msg('OK\n').
test_sort_neighbors :-
    retractall(failed_extraction(_)),
    assertz(failed_extraction(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_extract_plan :- 
    preamble_extraction,
    findall(edge(State, PrevState, Transition, Cost), edge(State, PrevState, Transition, Cost), Edges),
    extract_plan(
        [pred1],
        [],
        Edges,
        [],
        [action1],
        0,
        1
    ),
    extract_plan(
        [pred3],
        [],
        Edges,
        [],
        [action1, action4]
    ), !, 
    extract_plan(
        [pred1, pred2, pred3],
        [],
        Edges,
        [],
        [action2, action5, action7],
        0, 
        5
    ),
    retract(edge([pred1, pred2, pred3], [pred2, pred3], action7, 5)),
    retract(edge([pred1, pred2, pred3], [pred1, pred2], action9, 6)),
    assertz(edge([pred1, pred2, pred3], [pred2, pred3], action7, 6)),
    assertz(edge([pred1, pred2, pred3], [pred1, pred2], action9, 7)),
    findall(edge(State, PrevState, Transition, Cost), edge(State, PrevState, Transition, Cost), NewEdges),
    extract_plan(
        [pred1, pred2, pred3],
        [],
        NewEdges,
        [],
        [action1, action4, action8],
        0,
        5
    ),
    succ_msg('OK\n').
test_extract_plan :-
    retractall(failed_extraction(_)),
    assertz(failed_extraction(true)),
    fail_msg('FAIL\n').



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


run_all_plan_extraction_tests :-
    info_msg('RUNNING TEST FOR PLAN EXTRACTION... \n'), ! ,
    format('    Testing find_neighbors................... '), ! ,
    test_find_neighbors, ! ,
    format('    Testing sort_neighbors................... '), ! ,
    test_sort_neighbors, ! ,
    format('    Testing extract_plan..................... '), ! ,
    test_extract_plan, ! ,
    failed_extraction(Failed), \+Failed.