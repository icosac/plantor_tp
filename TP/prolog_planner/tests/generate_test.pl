:- ensure_loaded('../src/generate.pl').

:- dynamic agent/1.

:- dynamic failed_generation/1.
failed_generation(false).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_insert_open_by_cost :-
    Node1 = node(state1, prev1, action1, 5, depth1, invs1),
    Node2 = node(state2, prev2, action2, 3, depth2, invs2),
    Node3 = node(state3, prev3, action3, 5, depth3, invs3),
    insert_open_by_cost(Node1, [], [Node1]),
    insert_open_by_cost(Node2, [Node1], [Node2, Node1]),
    insert_open_by_cost(Node3, [Node2, Node1], [Node2, Node1, Node3]),
    succ_msg('OK\n').
    
test_insert_open_by_cost :-
    retract(failed_generation(_)),
    assertz(failed_generation(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_get_state_from_list :-
    List = [node([state1], prev1, action1, cost1, depth1, invs1), node([state2], prev2, action2, cost2, depth2, invs2)],
    get_state_from_list([state1], List, node([state1], prev1, action1, cost1, depth1, invs1)),
    get_state_from_list([state2], List, node([state2], prev2, action2, cost2, depth2, invs2)),
    \+ get_state_from_list([state3], List, _),
    succ_msg('OK\n').

test_get_state_from_list :-
    retract(failed_generation(_)),
    assertz(failed_generation(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_maybe_enqueue_successor :-
enable_graph_debug, 
format('\n'),
    assertz(hl_d_action(act1, [pred_s1], [pred_e1], [invs1], [add(eff1)], [del(pred1)], [1,2])),
    CurrentNode = node([state0], prev0, action0, 2, 0, [invs]),
    CLOSE = [node([state1], prev1, action1, 5, depth1, invs1)],
    OPEN0 = [node([state2], prev2, action2, 3, depth2, invs2)],
    NewState = [state3],
    NewInvariants = [invs3],
    maybe_enqueue_successor(CurrentNode, NewState, NewInvariants, start(act1), OPEN0, CLOSE, OPEN1),
    OPEN1 = [node([state2],prev2,action2,3,depth2,invs2),node([state3],[state0],start(act1),3,1,[invs3])],

format('\n'),

    maybe_enqueue_successor(CurrentNode, [state2], NewInvariants, end(act1), OPEN0, CLOSE, OPEN2),
    OPEN2 = OPEN0,

    succ_msg('OK\n').


test_maybe_enqueue_successor :-
    retract(failed_generation(_)),
    assertz(failed_generation(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_generate_states_start1 :-
    % Trivial case: no actions, no state, nothing to generate
    generate_states_start(
        [],
        [],
        [],
        [],
        1,
        1
    ),
    % Single action: adds eff1 to empty state
    generate_states_start(
        [],
        [hl_d_action(action1, _, _, _, [add(eff1)], [del(eff1)], _)],
        [],
        [entry([eff1], [], action1(start), [action1, _, [del(eff1)]], _, _)],
        1,
        1
    ),
    % Two actions: each adds a different effect to empty state
    generate_states_start(
        [],
        [
            hl_d_action(action1, _, _, _, [add(eff1)], [del(eff1)], _),
            hl_d_action(action2, _, _, _, [add(eff3)], [del(eff4)], _)
        ],
        [],
        [   
            entry([eff3], [], action2(start), [action2, _, [del(eff4)]], _, _),
            entry([eff1], [], action1(start), [action1, _, [del(eff1)]], _, _)
        ],
        1,
        1
    ),
    % Two actions: each adds and deletes predicates from a non-empty state
    generate_states_start(
        [pred1, pred2],
        [
            hl_d_action(action1, _, _, _, [add(eff1), del(pred1)], [del(eff1)], _),
            hl_d_action(action2, _, _, _, [add(eff3), del(pred2)], [del(eff4)], _)
        ],
        [],
        [
            entry([pred1, eff3], [pred1, pred2], action2(start), [action2, _, [del(eff4)]], _, _),
            entry([pred2, eff1], [pred1, pred2], action1(start), [action1, _, [del(eff1)]], _, _)
        ],
        1,
        1
    ),
    % Two actions: both add the same effect and delete the same predicate from a single-predicate state
    generate_states_start(
        [pred1],
        [
            hl_d_action(action1, _, _, _, [add(eff1), del(pred1)], [del(eff1)], _),
            hl_d_action(action2, _, _, _, [add(eff1), del(pred1)], [del(eff1)], _)
        ],
        [],
        [
            entry([eff1], [pred1], action2(start), [action2, _, [del(eff1)]], _, _),
            entry([eff1], [pred1], action1(start), [action1, _, [del(eff1)]], _, _)
        ],
        1,
        1
    ),
    % Two actions: one deletes both predicates, one deletes one and adds another
    generate_states_start(
        [pred1, pred2],
        [
            hl_d_action(action1, _, _, _, [add(eff1), del(pred1), del(pred2)], [del(eff1)], _),
            hl_d_action(action2, _, _, _, [add(eff2), del(pred1)], [del(eff2)], _)
        ],
        [],
        [
            entry([pred2, eff2],    [pred1, pred2], action2(start), [action2, _, [del(eff2)]], _, _),
            entry([eff1],           [pred1, pred2], action1(start), [action1, _, [del(eff1)]], _, _)
        ],
        1,
        1
    ),
    % Action with only delete effect
    generate_states_start(
        [pred1, pred2],
        [hl_d_action(action1, _, _, _, [del(pred1)], [], _)],
        [],
        [entry([pred2], [pred1, pred2], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    % Action with no effects
    generate_states_start(
        [pred1],
        [hl_d_action(action1, _, _, _, [], [], _)],
        [],
        [entry([pred1], [pred1], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    % Duplicate actions
    generate_states_start(
        [],
        [
          hl_d_action(action1, _, _, _, [add(eff1)], [del(eff1)], _), 
          hl_d_action(action1, _, _, _, [add(eff1)], [del(eff1)], _)
        ],
        [],
        [entry([eff1], [], action1(start), [action1, _, [del(eff1)]], _, _)],
        1,
        1
    ),
    % Action that adds and deletes the same predicate, ORDER MATTERS
    generate_states_start(
        [pred1],
        [hl_d_action(action1, _, _, _, [add(pred1), del(pred1)], [], _)],
        [],
        [entry([], [pred1], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    % Action that adds and deletes the same predicate, ORDER MATTERS
    generate_states_start(
        [pred1],
        [hl_d_action(action1, _, _, _, [del(pred1), add(pred1)], [], _)],
        [],
        [entry([pred1], [pred1], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    % Multiple actions with overlapping effects
    generate_states_start(
        [a],
        [
          hl_d_action(action1, _, _, _, [add(b), del(a)], [], _), 
          hl_d_action(action2, _, _, _, [add(a), del(b)], [], _)
        ],
        [],
        [
            entry([a], [a], action2(start), [action2, _, []], _, _),
            entry([b], [a], action1(start), [action1, _, []], _, _)
        ],
        1,
        1
    ),
    % Action with empty state and empty effects
    generate_states_start(
        [],
        [hl_d_action(action1, _, _, _, [], [], _)],
        [],
        [entry([], [], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    % Action with multiple add effects
    generate_states_start(
        [],
        [hl_d_action(action1, _, _, _, [add(a), add(b)], [], _)],
        [],
        [entry([a, b], [], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    % Action with multiple del effects
    generate_states_start(
        [a, b, c],
        [hl_d_action(action1, _, _, _, [del(a), del(b)], [], _)],
        [],
        [entry([c], [a, b, c], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    % Action with add and del that overlap with state
    generate_states_start(
        [a, b],
        [hl_d_action(action1, _, _, _, [add(c), del(a)], [], _)],
        [],
        [entry([b, c], [a, b], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    % Action with add and del that do not overlap with state
    generate_states_start(
        [a],
        [hl_d_action(action1, _, _, _, [add(b), del(c)], [], _)],
        [],
        [entry([a, b], [a], action1(start), [action1, _, []], _, _)],
        1,
        1
    ),
    succ_msg('OK\n').
test_generate_states_start1 :-
    retract(failed_generation(_)),
    assertz(failed_generation(true)),
    fail_msg('FAIL\n').

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

test_generate_states_start2 :-
    generate_states_start(
        [pos(a1, home), free(a1), tool(a1, cleaner), cylinders_stack(3)],
        [hl_d_action(move_arm(a1, home, tool_depot), _, _, _, [del(free(a1)), del(pos(a1, home))], [add(free(a1)), add(pos(a1, tool_depot))], _)],
        [],
        [S1_s],
        1,
        1
    ),
    S1_s = entry( [tool(a1, cleaner), cylinders_stack(3)], 
                  [pos(a1, home), free(a1), tool(a1, cleaner), cylinders_stack(3)], 
                  move_arm(start, a1, home, tool_depot), 
                  [move_arm(a1, home, tool_depot), _, [add(free(a1)), add(pos(a1, tool_depot))]], 
                  _, 
                  _
    ),
    generate_states_start(
        [free(a1), pos(a1, tool_depot), tool(a1, cleaner), cylinders_stack(3)],
        [hl_d_action(change_tool(a1, cleaner, two_finger_gripper), _, _, _, [del(free(a1)), del(tool(a1, cleaner))], [add(free(a1)), add(tool(a1, two_finger_gripper))], _)],
        [],
        [S2_s],
        1,
        1
    ),
    S2_s = entry( [pos(a1, tool_depot), cylinders_stack(3)], 
                  [free(a1), pos(a1, tool_depot), tool(a1, cleaner), cylinders_stack(3)], 
                  change_tool(start, a1, cleaner, two_finger_gripper), 
                  [change_tool(a1, cleaner, two_finger_gripper), _, [add(free(a1)), add(tool(a1, two_finger_gripper))]], 
                  _, 
                  _
    ),
    succ_msg('OK\n').
test_generate_states_start2 :-
    retract(failed_generation(_)),
    assertz(failed_generation(true)),
    fail_msg('FAIL\n').

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


test_generate_states_end :- 
    S1_s = entry( [tool(a1, cleaner), cylinders_stack(3)], 
                  [pos(a1, home), free(a1), tool(a1, cleaner), cylinders_stack(3)], 
                  move_arm_start(a1, home, tool_depot), 
                  [move_arm(a1, home, tool_depot), [not(pos(_, tool_depot))], [add(free(a1)), add(pos(a1, tool_depot))]], 
                  2, 
                  1
    ),
    generate_states_end(S1_s, [], [R1]),
    R1 = entry( [tool(a1, cleaner), cylinders_stack(3), free(a1), pos(a1, tool_depot)], 
                [tool(a1, cleaner), cylinders_stack(3)], 
                move_arm(end, a1, home, tool_depot), 
                [none, none, []], 
                3, 
                1
    ),
    S2_s = entry( [pos(a1, tool_depot), cylinders_stack(3)], 
                  [pos(a1, tool_depot), free(a1), tool(a1, cleaner), cylinders_stack(3)], 
                  change_tool_start(a1, cleaner, two_finger_gripper), 
                  [change_tool(a1, cleaner, two_finger_gripper), [not(tool(_, two_finger_gripper))], [add(free(a1)), add(tool(a1, two_finger_gripper))]], 
                  2, 
                  1
    ),
    generate_states_end(S2_s, [], [R2]),
    R2 = entry( [pos(a1, tool_depot), cylinders_stack(3), free(a1), tool(a1, two_finger_gripper)], 
                [pos(a1, tool_depot), cylinders_stack(3)], 
                change_tool(end, a1, cleaner, two_finger_gripper), 
                [none, none, []], 
                3, 
                1
    ),
    % This is a negative test: the end-preconditions are not satisfied so it returns the same list of open states (which in this case is empty)
    S3_s = entry( [tool(a1, cleaner), cylinders_stack(3), pos(a2, tool_depot)], 
                  [pos(a1, home), free(a1), tool(a1, cleaner), cylinders_stack(3)], 
                  move_arm_start(a1, home, tool_depot), 
                  [move_arm(a1, home, tool_depot), [not(pos(_, tool_depot))], [add(free(a1)), add(pos(a1, tool_depot))]], 
                  2, 
                  1
    ),
    generate_states_end(S3_s, [], []),
    succ_msg('OK\n').
test_generate_states_end :-
    retract(failed_generation(_)),
    assertz(failed_generation(true)),
    fail_msg('FAIL\n').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


run_all_generate_tests :-
    info_msg('RUNNING GENERATION TESTS...\n'),
    format('    Testing insert_open_by_cost.............. '),
    test_insert_open_by_cost, !,
    format('    Testing get_state_from_list.............. '),
    test_get_state_from_list, !,
    format('    Testing maybe_enqueue_successor.......... '),
    test_maybe_enqueue_successor, !,
    % format('    Testing generate_states_start1........... '),
    % test_generate_states_start1, !,  
    % format('    Testing generate_states_start2........... '),
    % test_generate_states_start2, !,
    % format('    Testing generate_states_end.............. '),
    % test_generate_states_end, !,
    failed_generation(false).