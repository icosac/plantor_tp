:- ensure_loaded('../src/utility.pl').

:- dynamic failed_utility/1.
failed_utility(false).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Tests for auxiliary functions
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

test_set_from_list :-
    set_from_list([1,2,3,4], [1,2,3,4]), ! ,
    set_from_list([1,2,3,4,4], [1,2,3,4]), ! ,
    set_from_list([], []), ! ,
    set_from_list([1,2,4,3,4,4], [1,2,4,3]), !,
    \+set_from_list([1,2,4,3,4,4], [1,4,3]), !,
    succ_msg('OK\n').
test_set_from_list :-
    retractall(failed_utility(_)),
    assertz(failed_utility(true)),
    fail_msg('FAIL\n').

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

test_equal_sets :- 
    equal_sets([1,2,3,4], [1,2,3,4]), ! ,
    \+equal_sets([1,2,3,4,5], [1,2,3,4]), ! ,
    equal_sets([], []), ! ,
    \+equal_sets([1,2,3,4], [1,2,3,4,5]), ! ,
    \+equal_sets([1,3,4], [1,2,4]), ! ,
    succ_msg('OK\n').
test_equal_sets :- 
    retractall(failed_utility(_)),
    assertz(failed_utility(true)),
    fail_msg('FAIL\n').

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

test_remove_element_from_list :-
    remove_one_element_from_list(1, [1,2,3,4], [2,3,4]), ! ,
    remove_one_element_from_list(2, [1,2,2,3], [1,2,3]), ! ,
    remove_one_element_from_list(3, [1,3,4,3], [1,4,3]), ! ,
    remove_one_element_from_list(1, [3,4,3], [3,4,3]), ! ,
    remove_one_element_from_list(1, [], []), ! ,
    succ_msg('OK\n').
test_remove_element_from_list :-
    retractall(failed_utility(_)),
    assertz(failed_utility(true)),
    fail_msg('FAIL\n').

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

test_equal_lists :- 
    equal_lists([1,2,3,4], [1,2,3,4]), ! ,
    \+equal_lists([1,2,3,4,5], [1,2,3,4]), ! ,
    equal_lists([], []), ! ,
    \+equal_lists([1,2,3,4], [1,2,3,4,5]), ! ,
    \+equal_lists([1,3,4], [1,2,4]), ! ,
    \+equal_lists([1,2,3,2], [1,2,3,3]), ! ,
    succ_msg('OK\n').
test_equal_lists :- 
    retractall(failed_utility(_)),
    assertz(failed_utility(true)),
    fail_msg('FAIL\n').
    
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

run_all_utility_tests :-
    info_msg('RUNNING TEST FOR AUXILIARY FUNCTIONS... \n'), ! ,
    format('    Testing set_from_list.................... '), ! ,
    test_set_from_list, ! ,
    format('    Testing equal_sets....................... '), ! ,
    test_equal_sets, ! ,
    format('    Testing remove_one_element_from_list..... '), ! ,
    test_remove_element_from_list, ! ,
    format('    Testing equal_lists...................... '), ! ,
    test_equal_lists,
    failed_utility(Failed), \+Failed.
