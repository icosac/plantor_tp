:- ensure_loaded('../src/applicability.pl').

:- dynamic agent/1.
:- dynamic init/1.
:- dynamic hl_d_action/7.

:- dynamic preamble_done/1.
preamble_done(false).

:- dynamic failed_applicability/1.
failed_applicability(false).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


preamble :-
    preamble_done(false),
    retractall(init(_)),
    retractall(agent(_)),
    retractall(hl_d_action(_, _, _, _, _, _, _)),
    assertz(init([
        pos(a1, home), 
        free(a1), 
        tool(a1, two_finger_gripper),
        cylinders_stack(3)
    ])),
    assertz(agent(a1)),
    retract(preamble_done(false)),
    assertz(preamble_done(true)),
    true.
preamble :- true.


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_hl_is_state_goal :-
    preamble,
    init(Init),
    hl_is_state_goal(
        [pos(a1, home), free(a1), tool(a1, two_finger_gripper), cylinders_stack(3)],
        Init
    ),
    \+hl_is_state_goal(
        [pos(a1, home), tool(a1, two_finger_gripper), cylinders_stack(3)],
        Init
    ),
    \+hl_is_state_goal(
        [pos(a1, home), free(a2), tool(a1, two_finger_gripper), cylinders_stack(3)],
        Init
    ),
    hl_is_state_goal(
        [pos(a1, home), free(a1), tool(a1, two_finger_gripper), cylinders_stack(3), test(one_more_predicate)],
        [pos(a1, home), free(a1), tool(a1, two_finger_gripper), cylinders_stack(3)]
    ),
    hl_is_state_goal(
        [pos(a1, home), free(a1), tool(a1, two_finger_gripper), cylinders_stack(3)],
        [pos(a1, home), free(a1), ll_robot_at(r1, location1)]
    ),
    succ_msg('OK\n').

test_hl_is_state_goal :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_verify_preconditions :-
    preamble,
    init(Init),
    verify_preconditions(Init, [pos(a1, home)]),
    verify_preconditions(Init, [pos(a1, home), free(a1)]),
    \+verify_preconditions(Init, [pos(a100, home)]),
    \+verify_preconditions(Init, [pos(a1, home), free(a1), tool(a2, two_finger_gripper)]),
    \+verify_preconditions(Init, [neg(free(a1))]),
    \+verify_preconditions(Init, [neg(free(a1)), neg(free(a2))]),
    verify_preconditions(Init, [free(a1), neg(free(a2))]),
    \+verify_preconditions(Init, [free(a2), neg(free(a1))]),
    assertz(agent(a2)),
    \+verify_preconditions(Init, [agent(Agent), free(Agent), Agent=a2]),
    assertz(value(3)),
    verify_preconditions(Init, [value(X), cylinders_stack(X)]),
    retract(agent(a2)),
    retract(value(3)),
    succ_msg('OK\n').
    
test_verify_preconditions :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_invariants_check :-
    preamble,
    invariants_check([free(a1)], [add(pos(a1, home)), add(tool(a1, two_finger_gripper))]),
    \+invariants_check([free(a1)], [del(free(a1)), add(pos(a1, home))]),
    \+invariants_check([tool(a1, two_finger_gripper)], [del(tool(a1, two_finger_gripper)), add(pos(a1, home))]),
    invariants_check([], [add(pos(a1, home)), del(free(a2))]),
    succ_msg('OK\n').
test_invariants_check :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_applicable_hl_action :-
    preamble,
    init(Init),
    assertz(agent(a1)),
    % Check that the precondition check works correctly
    applicable_hl_action(
        Init,
        [],
        [agent(Agent), free(Agent)],
        []
    ),
    applicable_hl_action(
        Init, 
        [],
        [agent(Agent), free(Agent), pos(Agent, home)], 
        []
    ),
    \+applicable_hl_action(
        Init, 
        [],
        [agent(Agent), neg(free(Agent))],
        []
    ),
    \+applicable_hl_action(
        Init, 
        [],
        [agent(Agent), pos(Agent, home), neg(free(Agent))],
        []
    ),
    \+applicable_hl_action(
        Init, 
        [],
        [agent(Agent), free(Agent), neg(free(Agent))],
        []
    ),

    % Check that the effects do not violate invariants correctly
    applicable_hl_action(
        Init, 
        [free(a1)],
        [agent(a1), free(a1)],
        []
    ),
    \+applicable_hl_action(
        Init, 
        [free(a1)],
        [agent(a1), free(a1)],
        [del(free(a1))]
    ),
    \+applicable_hl_action(
        Init, 
        [free(a1), tool(a1, two_finger_gripper)],
        [agent(a1), free(a1), tool(a1, two_finger_gripper)],
        [del(free(a1)), add(tool(a1, suction_cup))]
    ),
    applicable_hl_action(
        Init, 
        [free(a1), tool(a1, two_finger_gripper)],
        [agent(a1), free(a1), tool(a1, two_finger_gripper)],
        [add(tool(a1, suction_cup))]
    ),

    retract(agent(a1)),
    succ_msg('OK\n').
test_applicable_hl_action :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_applicable_hl_start_actions :-
    preamble,
    init(Init),
    assertz(agent(a1)),
    assertz(
        hl_d_action(action1, 
            [],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action2(a1),
            [free(a1)],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action3(Agent),
            [agent(Agent), free(Agent)],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action4(Agent),
            [agent(Agent), free(Agent), neg(pos(Agent, tool_depot))],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action5(Agent),
            [agent(Agent), free(Agent), neg(pos(Agent, home))],
            [],
            [],
            [],
            [],
            []
        )
    ),
    applicable_hl_start_actions(Init, [], L1), !,
    list_to_action_names(L1, [action1,action2(a1),action3(a1),action4(a1)]), !,

    assertz(agent(a2)),
    append(Init, [free(a2), pos(a2, cylinders_box)], InitWithA2),
    applicable_hl_start_actions(InitWithA2, [], L2), !,
    list_to_action_names(L2, [action1,action2(a1),action3(a1),action3(a2),action4(a1),action4(a2),action5(a2)]),
    
    assertz(
        hl_d_action(action6(Agent),
            [agent(Agent), free(Agent)],
            [],
            [pos(_, home)],
            [],
            [],
            [],
            []
        )
    ),
    applicable_hl_start_actions(InitWithA2, [], L3), !,
    list_to_action_names(L3, [action1,action2(a1),action3(a1),action3(a2),action4(a1),action4(a2),action5(a2)]),
    
    assertz(
        hl_d_action(action7(Agent),
            [agent(Agent), free(Agent)],
            [],
            [invalid_overall],
            [],
            [add(invalid_overall)],
            [],
            []
        )
    ),
    applicable_hl_start_actions(InitWithA2, [], L4), !,
    list_to_action_names(L4, [action1,action2(a1),action3(a1),action3(a2),action4(a1),action4(a2),action5(a2)]),

    Init2 = [at(c1,location1), at(c2,location1), at(r1,location1), available(r1), available(crane2), located(crane1,location1), located(crane2,location2), ll_robot_at(r1,location1), ll_gripper(crane1,open), ll_gripper(crane2,open), ll_crane_at(crane1,location1), ll_crane_at(crane2,location2), onground(c2), clear(c1), onground(c1), clear(c2), available(crane1)],
    retractall(hl_d_action(_, _, _, _, _, _, _)),
    assertz(location(location1)),
    assertz(location(location2)),
    assertz(connected(location1, location2)),
    assertz(connected(location2, location1)),
    assertz(container(c1)),
    assertz(container(c2)),
    assertz(robot(r1)),
    assertz(crane(crane1)),
    assertz(crane(crane2)),
    assertz(hl_d_action(
        crane_load_robot(Crane, Robot, Container, Location),
        [
            crane(Crane),
            robot(Robot),
            available(Crane),
            available(Robot),
            location(Location),
            located(Crane, Location),
            at(Robot, Location),
            at(Container, Location),
            container(Container),
            clear(Container),
            onground(Container)
        ],
        [],
        [],
        [
            del(available(Crane)),
            del(available(Robot)),
            del(onground(Container))
        ],
        [
            add(on(Container, Robot)),
            add(clear(Container)),
            add(available(Crane)),
            add(available(Robot))
        ],
        [1, 2]
        )
    ),
    applicable_hl_start_actions(Init2, [], L5), !,
    list_to_action_names(L5, [crane_load_robot(crane1,r1,c1,location1), crane_load_robot(crane1,r1,c2,location1)]),

    succ_msg('OK\n').

test_applicable_hl_start_actions :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_applicable_hl_end_actions :-
    preamble,
    retractall(hl_d_action(_, _, _, _, _, _, _)),
    init(Init),
    append(
        Init, 
        [
            executing(action1), 
            executing(action2(a1)),
            executing(action3(a1)),
            executing(action4(a1))
        ], 
        InitWithExecuting
    ),
    assertz(agent(a1)),
    assertz(
        hl_d_action(action1, 
            [],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action2(a1),
            [],
            [free(a1)],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action3(Agent),
            [],
            [agent(Agent), free(Agent)],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action4(Agent),
            [],
            [agent(Agent), free(Agent), neg(pos(Agent, tool_depot))],
            [],
            [],
            [],
            []
        )
    ),
    applicable_hl_end_actions(InitWithExecuting, [], L1), !,
    list_to_action_names(L1, [action1,action2(a1),action3(a1),action4(a1)]),

    append(InitWithExecuting, [executing(action3(a2)), executing(action4(a2))], InitWithA2),
    applicable_hl_end_actions(InitWithA2, [], L2), !,
    list_to_action_names(L2, [action1,action2(a1),action3(a1),action4(a1)]),

    append(InitWithA2, [free(a2), pos(a2, tool_depot)], InitWithA2Facts1),
    assertz(agent(a2)),
    applicable_hl_end_actions(InitWithA2Facts1, [], L3), !,
    list_to_action_names(L3, [action1,action2(a1),action3(a1),action4(a1),action3(a2)]),

    append(InitWithA2, [free(a2), pos(a2, cylinders_box)], InitWithA2Facts2),
    assertz(agent(a2)),
    applicable_hl_end_actions(InitWithA2Facts2, [], L4), !,
    list_to_action_names(L4, [action1,action2(a1),action3(a1),action4(a1),action3(a2),action4(a2)]),
    succ_msg('OK\n').

test_applicable_hl_end_actions :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_applicable_hl_d_actions :-
    preamble,
    retractall(hl_d_action(_, _, _, _, _, _, _)),
    retractall(agent(_)),
    assertz(agent(a1)),
    assertz(
        hl_d_action(action1, 
            [],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action2(a1),
            [free(a1)],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action3(Agent),
            [agent(Agent), free(Agent)],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action4(Agent1, Agent2),
            [agent(Agent1), agent(Agent2), free(Agent1), neg(free(Agent2))],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action5(Agent),
            [agent(Agent), free(Agent), neg(pos(Agent, tool_depot))],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action6(Agent),
            [agent(Agent)],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(not_applicable_action,
            [non_existent_predicate],
            [],
            [],
            [],
            [],
            []
        )
    ),
    init(Init),
    applicable_hl_actions(Init, [], L1Start, L1End), !,
    list_to_action_names(L1Start, L1StartNames),
    list_to_action_names(L1End, []),
    equal_lists([action1,action2(a1),action3(a1),action5(a1),action6(a1)], L1StartNames),
    \+member(not_applicable_action, L1StartNames),
    
    assertz(agent(a2)),
    applicable_hl_actions(Init, [], L2Start, L2End), !,
    list_to_action_names(L2Start, L2StartNames),
    list_to_action_names(L2End, []),
    equal_lists([
        action1,
        action2(a1),
        action3(a1),
        action5(a1),
        action4(a1,a2), 
        action6(a1),
        action6(a2)], 
        L2StartNames
    ),
    \+member(not_applicable_action, L2StartNames),

    append(Init, [executing(action1)], InitWithExecuting),
    applicable_hl_actions(InitWithExecuting, [], L3Start, L3End), !,
    list_to_action_names(L3Start, L3StartNames),
    list_to_action_names(L3End, [action1]),
    equal_lists([
        action1,
        action2(a1),
        action3(a1),
        action5(a1),
        action4(a1,a2), 
        action6(a1),
        action6(a2)], 
        L3StartNames
    ),
    \+member(not_applicable_action, L3StartNames),
    succ_msg('OK\n').

test_applicable_hl_d_actions :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_why_not_applicable_hl_action :-
    preamble,
    retractall(hl_d_action(_, _, _, _, _, _, _)),
    init(Init),
    why_not_applicable_hl_action(Init, [], action_does_not_exist, start, UnknownResult),
    UnknownResult = not_applicable(unknown_action(action_does_not_exist)),

    assertz(
        hl_d_action(action1,
            [],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action2,
            [free(a1), pos(a1, tool_depot)],
            [],
            [],
            [],
            [],
            []
        )
    ),
    why_not_applicable_hl_action(Init, [], action1, end, NotExecutingResult),
    NotExecutingResult = not_applicable(not_executing(action1)),
    why_not_applicable_hl_action(Init, [], action2, start, StartNotApplicableResult),
    StartNotApplicableResult = not_applicable(
        start_preconditions_violated(
            [free(a1), pos(a1, tool_depot)],
            [pos(a1, tool_depot)]
        )
    ),

    append(Init, [executing(action1)], InitWithExecuting),
    why_not_applicable_hl_action(InitWithExecuting, [], action1, end, ApplicableResult),
    ApplicableResult = applicable(end),
    succ_msg('OK\n').
test_why_not_applicable_hl_action :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').

list_to_action_names([], []).
list_to_action_names([H|T], Ret) :-
    list_to_action_names([H|T], [], Ret).
list_to_action_names([], Ret, Ret).
list_to_action_names([hl_action(Name, _, _, _)|T], List, Ret) :-
    append(List, [Name], NewList),
    list_to_action_names(T, NewList, Ret).
list_to_action_names([hl_d_action(Name, _, _, _, _, _, _)|T], List, Ret) :-
    append(List, [Name], NewList),
    list_to_action_names(T, NewList, Ret).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_executing_invariants :-
    preamble,
    retractall(hl_d_action(_, _, _, _, _, _, _)),
    retractall(agent(_)),
    assertz(agent(a1)),
    assertz(agent(a2)),
    assertz(
        hl_d_action(action1, 
            [],
            [],
            [inv1, inv2],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action2,
            [],
            [],
            [inv2, inv3],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action3,
            [],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action4(a1),
            [],
            [],
            [fixed(a1)],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action5(Agent),
            [agent(Agent)],
            [],
            [carrying(Agent)],
            [],
            [],
            []
        )
    ),
    executing_invariants(
        [executing(action1), executing(action2), executing(action3), executing(action4(a1)), executing(action5(a2))],
        Invariants
    ),
    sort([inv1,inv2,inv2,inv3,fixed(a1),carrying(a2)], SortedInvariants),
    sort(Invariants, SortedInvariants),
    succ_msg('OK\n').
test_executing_invariants :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_executing_invariants_excluding :-
    preamble,
    retractall(hl_d_action(_, _, _, _, _, _, _)),
    retractall(agent(_)),
    assertz(agent(a1)),
    assertz(agent(a2)),
    assertz(
        hl_d_action(action1, 
            [],
            [],
            [inv1, inv2],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action2,
            [],
            [],
            [inv2, inv3],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action3,
            [],
            [],
            [],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action4(a1),
            [],
            [],
            [fixed(a1)],
            [],
            [],
            []
        )
    ),
    assertz(
        hl_d_action(action5(Agent),
            [agent(Agent)],
            [],
            [carrying(Agent)],
            [],
            [],
            []
        )
    ),
    executing_invariants_excluding(
        [executing(action1), executing(action2), executing(action3), executing(action4(a1)), executing(action5(a2))],
        action2,
        Invariants
    ),
    sort([inv1,inv2,fixed(a1),carrying(a2)], SortedInvariants),
    sort(Invariants, SortedInvariants),

    executing_invariants_excluding(
        [executing(action1), executing(action2), executing(action3), executing(action4(a1)), executing(action5(a2))],
        action5(a2),
        NewInvariants
    ),
    sort([inv1,inv2,inv2,inv3,fixed(a1)], SortedNewInvariants),
    sort(NewInvariants, SortedNewInvariants),
    succ_msg('OK\n').


test_executing_invariants_excluding :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_apply_effects :-
    apply_effects(           
        [add(pred1)],
        [],
        [pred1]
    ),
    apply_effects(           
        [add(pred1), add(pred1)],
        [],
        [pred1]
    ),
    apply_effects(           
        [add(pred1), add(pred1), del(pred1)],
        [],
        []
    ),
    apply_effects(           
        [add(pred(pred1))],
        [],
        [pred(pred1)]
    ),
    apply_effects(           
        [add(pred(pred1)), add(pred1), add(pred2)],
        [],
        [pred(pred1), pred1, pred2]
    ),
    apply_effects(           
        [del(pred1)],
        [],
        []
    ),
    apply_effects(           
        [add(pred(pred1)), del(pred(pred2))],
        [pred(pred2)],
        [pred(pred1)]
    ),
    apply_effects(           
        [add(pred(pred1))],
        [pred(pred1)],
        [pred(pred1)]
    ),
    apply_effects(           
        [add(pred(pred1, pred2)), del(pred1), del(pred2)],
        [pred1, pred2],
        [pred(pred1, pred2)]
    ),
    succ_msg('OK\n').
test_apply_effects :-
    retract(failed_applicability(_)),
    assertz(failed_applicability(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


run_all_applicability_tests :-
    info_msg('RUNNING APPLICABILITY TESTS...\n'),
    format('    Testing hl_is_state_goal................. '), !,
    test_hl_is_state_goal, !, 
    format('    Testing verify_preconditions............. '), !,
    test_verify_preconditions, !,
    format('    Testing invariants_check................. '), !,
    test_invariants_check, !,
    format('    Testing applicable_hl_action............. '), !,
    test_applicable_hl_action, !, 
    format('    Testing applicable_hl_start_actions...... '), !,
    test_applicable_hl_start_actions, !,
    format('    Testing applicable_hl_end_actions........ '), !,
    test_applicable_hl_end_actions, !,
    format('    Testing applicable_hl_d_actions.......... '), !,
    test_applicable_hl_d_actions, !, 
    format('    Testing why_not_applicable_hl_action..... '), !,
    test_why_not_applicable_hl_action, !,
    format('    Testing executing_invariants............. '), !,
    test_executing_invariants, !,
    format('    Testing executing_invariants_excluding... '), !,
    test_executing_invariants_excluding, !,
    format('    Testing apply_effects.................... '), !,
    test_apply_effects, !,
    failed_applicability(Failed), \+Failed.
