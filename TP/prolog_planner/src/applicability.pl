:-ensure_loaded('../src/utility.pl').
:-ensure_loaded('../src/time_debug.pl').

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* This function checks if a state is the goal.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
hl_is_state_goal(_, []).
hl_is_state_goal(State, [H|T]) :-
    (
        ll_prefixed_literal(H)
        -> hl_is_state_goal(State, T)
        ;  memberchk(H, State),
           hl_is_state_goal(State, T)
    ).

ll_prefixed_literal(neg(Lit)) :-
    !,
    ll_prefixed_literal(Lit).
ll_prefixed_literal(Lit) :-
    atom(Lit),
    atom_concat('ll_', _, Lit),
    !.
ll_prefixed_literal(Lit) :-
    compound(Lit),
    compound_name_arity(Lit, Name, _),
    atom(Name),
    atom_concat('ll_', _, Name).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* This predicate checks that the preconditions of an action are applicable in a state.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
verify_preconditions(_State, []).
verify_preconditions(State, [HPre|Tail]) :-
    (HPre = neg(NegativePre))
    ->(
        \+memberchk(NegativePre, State),
        verify_preconditions(State, Tail)
    );(
        (
            member(HPre, State)
            *->(
                true
            );(
                (predicate_property(HPre, visible),
                 \+predicate_property(HPre, imported_from(pce_principal)))
                ->(
                    HPre
                );(
                    fail
                )
            )
        ),
        verify_preconditions(State, Tail)
    ).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* This predicate checks if a HL action is applicable in the current state.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
applicable_hl_action(State, Invariants, Preconditions, Effects) :-
    time_call(verify_preconditions(State, Preconditions), VerifyPreconditionsTime),
    time_emit('[applicable_hl_action] Time taken for verify_preconditions ~w\n', [VerifyPreconditionsTime]), 
    time_call(invariants_check(Invariants, Effects), InvariantsCheckTime),
    time_emit('[applicable_hl_action] Time taken for invariants_check ~w\n', [InvariantsCheckTime]).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* This predicate checks if the effects of a HL action violate the current invariants.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
invariants_check([], _Effects).
% If there is a positive invariant, check that it is not being deleted
invariants_check([HInv|TInv], Effects) :-
    HInv \= neg(_),
    \+member(del(HInv), Effects),
    invariants_check(TInv, Effects).
% If there is a negative invariant, check that its positive form is not being added
invariants_check([neg(HInv)|TInv], Effects) :-
    \+member(add(HInv), Effects),
    invariants_check(TInv, Effects).
invariants_check(_, _) :- fail.


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* This predicate finds all the applicable HL actions in a state, by checking their preconditions 
%  and invariants.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
applicable_hl_start_actions(_State, _Invariants, [], HLStartActions, HLStartActions).
applicable_hl_start_actions(State, Invariants, [H_HLAction|Tail], HLStartActions, RetHLActions) :-
    copy_term(H_HLAction, GroundedAction),
    GroundedAction = hl_d_action(Name, PreconditionsStart, _PreconditionsEnd, Overall, EffectsStart, _EffectsEnd, _Duration),
    debug_format('[applicable_hl_start_actions/5] Checking applicability of start action ~w with preconditions ~w\n', [Name, PreconditionsStart]),
    append(PreconditionsStart, Overall, MergedPreconditions),
    % Adding action overalls to the invariants to check at start
    append(Invariants, Overall, InvariantsForStart),
    applicable_hl_action(State, InvariantsForStart, MergedPreconditions, EffectsStart),
    (
        debug_format('[applicable_hl_start_actions/5] Action ~w is applicable in state ~w\n', [Name, State]),
        \+member(GroundedAction, HLStartActions) 
        ->(
            debug_format('[applicable_hl_start_actions/5] Adding action ~w to list of actions\n', [Name]),
            append(HLStartActions, [GroundedAction], TmpHLActions)
        );(
            debug_format('[applicable_hl_start_actions/5] Action is already present in list of actions ~w\n', [HLStartActions]),
            fail
        )
    ),
    applicable_hl_start_actions(State, Invariants, [H_HLAction|Tail], TmpHLActions, RetHLActions).
applicable_hl_start_actions(State, Invariants, [_H_HLAction|Tail], HLStartActions, RetHLActions) :-
    applicable_hl_start_actions(State, Invariants, Tail, HLStartActions, RetHLActions).

applicable_hl_start_actions(State, Invariants, HLStartActions) :-
    findall(
        hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration),
        hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration),
        AllHLActions
    ),
    debug_format('[applicable_hl_start_actions/3] Found HL actions in the KB\n'),
    print_list(AllHLActions),
    applicable_hl_start_actions(State, Invariants, AllHLActions, [], HLStartActions).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* This predicate finds all the HL actions that are executing in a state and whose preconditions at
%  end are satisfied, checking also the invariants.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
applicable_hl_end_actions(_State, _Invariants, [], HLEndActions, HLEndActions).
applicable_hl_end_actions(State, Invariants, [H_HLAction|Tail], HLEndActions, RetHLEndActions) :-
    % No need to merge overall and end preconditions, as overall preconditions are enforced before applying effects of other actions.
    H_HLAction = hl_d_action(Name, _PreconditionsStart, PreconditionsEnd, _Overall, _EffectsStart, EffectsEnd, _Duration),
    % Remove overall preconditions from Invariants to check at end
    % subtract(Invariants, Overall, InvariantsForEnd),
    executing_invariants_excluding(State, Name, InvariantsForEnd),
    debug_format('[applicable_hl_end_actions/5] Checking applicability of end action ~w\n', [Name]),
    ( 
        applicable_hl_action(State, InvariantsForEnd, PreconditionsEnd, EffectsEnd)
        ->(
            debug_format('[applicable_hl_end_actions/5] End Action ~w is applicable in state ~w\n', [Name, State]),
            \+member(H_HLAction, HLEndActions) 
            ->(
                append(HLEndActions, [H_HLAction], TmpHLEndActions)
            );(
                debug_format('[applicable_hl_end_actions/5] End action ~w is already present in list of actions ~w\n', [Name, HLEndActions]),
                fail
            )
        );(
            debug_format('[applicable_hl_end_actions/5] End Action ~w is not applicable in state ~w\n', [Name, State]),
            fail
        )
    ),
    applicable_hl_end_actions(State, Invariants, Tail, TmpHLEndActions, RetHLEndActions).
applicable_hl_end_actions(State, Invariants, [_H_HLAction|Tail], HLEndActions, RetHLEndActions) :-
    applicable_hl_end_actions(State, Invariants, Tail, HLEndActions, RetHLEndActions).

applicable_hl_end_actions(State, Invariants, HLEndActions) :-
    % Look through the state and take all the predicates of the form executing(ActionName)
    findall(
        ActionName,
        member(executing(ActionName), State),
        ExecutingActions
    ),
    debug_format('[applicable_hl_end_actions/3] Actions of type executing in current state: ~w\n', [ExecutingActions]),
    findall(
        hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration),
        (
            member(Name, ExecutingActions),
            hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration)
        ),
        AllHLEndActions
    ),
    debug_format('[applicable_hl_end_actions/3] Found HL end actions in the current state\n'),
    print_list(AllHLEndActions),
    % leash(-all), trace,
    applicable_hl_end_actions(State, Invariants, AllHLEndActions, [], HLEndActions).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* Get all applicable HL actions (start and end) in a state.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
applicable_hl_actions(State, Invariants, HLStartActions, HLEndActions) :-
    applicable_hl_start_actions(State, Invariants, HLStartActions),
    % HLEndActions = [],
    applicable_hl_end_actions(State, Invariants, HLEndActions),
    true.

applicable_hl_actions(_, _, [], []).




%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* Collect overall invariants for all executing actions in a state.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
executing_invariants(State, Invariants) :-
  ( 
    current_predicate(hl_d_action/7)
    ->(
        findall(
            Inv,
            ( 
                member(executing(ActionName), State),
                hl_d_action(ActionName, _PreStart, _PreEnd, Overall, _EffStart, _EffEnd, _Dur),
                member(Inv, Overall)
            ),
            Invariants
        )
    );(
        Invariants = []
    )
  ).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* Collect overall invariants for all executing actions in a state, excluding a given action.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
executing_invariants_excluding(_State, Name, _InvariantsForEnd) :-
    \+ground(Name),
    fatal_msg('[executing_invariants_excluding] Error in executing_invariants_excluding/3: Name must be ground, got ~w\n', [Name]).

executing_invariants_excluding(State, Name, InvariantsForEnd) :-
    findall(
        Inv,
        ( 
            member(executing(Other), State),
            Other \= Name,
            hl_d_action(Other, _PreS, _PreE, Overall, _EffS, _EffE, _Dur),
            member(Inv, Overall)
        ),
        InvariantsForEnd
    ),
    true.
    

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%* This function applies the effects to the current state and returns a new one.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
apply_effects([], State, State).
apply_effects([add(E)|T], State, RetState) :-
    \+member(E, State) % Only add if it is not already in the state
    ->(
        append(State, [E], NewState),
        apply_effects(T, NewState, RetState)
    );(
        apply_effects(T, State, RetState)
    ). % If it is already in the state, just continue
apply_effects([del(E)|T], State, RetState) :-
    subtract(State, [E], NewState),
    apply_effects(T, NewState, RetState).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

why_not_applicable_hl_action(State, Invariants, HLActionName, When) :-
    why_not_applicable_hl_action(State, Invariants, HLActionName, When, Result),
    explain_why_not_applicable_result(State, Invariants, HLActionName, Result).

why_not_applicable_hl_action(State, Invariants, HLActionName, When, Result) :-
    (
        \+hl_d_action(HLActionName, _, _, _, _, _, _)
        -> Result = not_applicable(unknown_action(HLActionName))
        ; hl_d_action(HLActionName, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, _),
          (
              When == end,
              \+memberchk(executing(HLActionName), State)
              -> Result = not_applicable(not_executing(HLActionName))
              ; \+verify_preconditions(State, Overall)
                -> Result = not_applicable(overall_preconditions_violated(Overall))
                ; (
                    When == start
                    -> (
                        \+verify_preconditions(State, PreconditionsStart)
                        -> failed_preconditions(State, PreconditionsStart, FailedPreconditionsStart),
                           Result = not_applicable(start_preconditions_violated(PreconditionsStart, FailedPreconditionsStart))
                        ; append(Invariants, Overall, InvariantsForStart),
                          \+invariants_check(InvariantsForStart, EffectsStart)
                          -> Result = not_applicable(invariants_violated(InvariantsForStart))
                          ; Result = applicable(start)
                    )
                    ; (
                        When == end
                        -> (
                            \+verify_preconditions(State, PreconditionsEnd)
                            -> Result = not_applicable(end_preconditions_violated(PreconditionsEnd))
                            ; append(Invariants, Overall, InvariantsForEnd),
                              \+invariants_check(InvariantsForEnd, EffectsEnd)
                              -> Result = not_applicable(invariants_violated(InvariantsForEnd))
                              ; Result = applicable(end)
                        )
                        ; Result = not_applicable(invalid_phase(When))
                    )
                  )
          )
    ),
    true.

failed_preconditions(_State, [], []).
failed_preconditions(State, [Precondition|Tail], Failed) :-
    (
        verify_preconditions(State, [Precondition])
        -> failed_preconditions(State, Tail, Failed)
        ; failed_preconditions(State, Tail, FailedTail),
          Failed = [Precondition|FailedTail]
    ).

explain_why_not_applicable_result(_State, _Invariants, _HLActionName, not_applicable(unknown_action(HLActionName))) :-
    format('Unknown HL action ~w\n', [HLActionName]).
explain_why_not_applicable_result(State, _Invariants, HLActionName, not_applicable(not_executing(HLActionName))) :-
    format('Action ~w is not executing in state ~w\n', [HLActionName, State]).
explain_why_not_applicable_result(State, _Invariants, HLActionName, not_applicable(overall_preconditions_violated(_Overall))) :-
    format('Overall preconditions are violated in state ~w for action ~w\n', [State, HLActionName]).
explain_why_not_applicable_result(State, _Invariants, HLActionName, not_applicable(start_preconditions_violated(_PreconditionsStart))) :-
    format('Start preconditions are violated in state ~w for action ~w\n', [State, HLActionName]).
explain_why_not_applicable_result(State, _Invariants, HLActionName, not_applicable(start_preconditions_violated(_PreconditionsStart, FailedPreconditionsStart))) :-
    format('Start preconditions are violated in state ~w for action ~w. Failed preconditions: ~w\n', [State, HLActionName, FailedPreconditionsStart]).
explain_why_not_applicable_result(State, _Invariants, HLActionName, not_applicable(end_preconditions_violated(_PreconditionsEnd))) :-
    format('End preconditions are violated in state ~w for action ~w\n', [State, HLActionName]).
explain_why_not_applicable_result(State, _Invariants, HLActionName, not_applicable(invariants_violated(Invariants))) :-
    format('Action ~w violates invariants ~w in state ~w\n', [HLActionName, Invariants, State]).
explain_why_not_applicable_result(State, Invariants, HLActionName, applicable(start)) :-
    format('Action ~w is applicable at start in state ~w with invariants ~w\n', [HLActionName, State, Invariants]).
explain_why_not_applicable_result(State, Invariants, HLActionName, applicable(end)) :-
    format('Action ~w is applicable at end in state ~w with invariants ~w\n', [HLActionName, State, Invariants]).
explain_why_not_applicable_result(_State, _Invariants, HLActionName, not_applicable(invalid_phase(When))) :-
    format('Invalid phase ~w for action ~w\n', [When, HLActionName]).
