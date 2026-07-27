%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%                                  MAPPINGS                                  %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% This function applies the mappings of an action. It also checks that the ll action is applicable 
% and changes the state accordingly 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
apply_mappings(Init, HL_Plan, LL_Plan) :-
  debug_format('[apply_mappings1] The HL plan is ~w\n', [HL_Plan]),
  apply_mappings(Init, HL_Plan, [], LL_Plan),
  debug_format('[apply_mappings1] Finished applying mappings ~w\n', [LL_Plan]).
  

apply_mappings(_, [], LL_Plan, LL_Plan) :-
  debug_format('[apply_mappings2] Reached this point ~w\n', [LL_Plan]),
  true.


apply_mappings(State, [HL_Step|T_HL_Actions], Plan, RetPlan) :-
  normalize_hl_step(HL_Step, StepLabel, Timing, HL_Action),
  debug_format('\n\n[apply_mappings3] HL step: ~w\n', [HL_Step]), 
  debug_format('[apply_mappings3] Normalized step: ~w\n', [StepLabel]), 
  length(Plan, Length),  
  append([Length-StepLabel], Plan, TempPlan),
  debug_format('[apply_mappings3] HL Action: ~w\n', [HL_Action]),
  debug_format('[apply_mappings3] Timing: ~w\n', [Timing]),
  hl_d_action(HL_Action, _, _, _, EffectsStart, EffectsEnd, _),
  apply_mappings(Timing, State, HL_Action, EffectsStart, EffectsEnd, T_HL_Actions, TempPlan, RetPlan).
  
apply_mappings(start, State, NewAction, Effects, _, T_HL_Actions, TempPlan, RetPlan) :-
  debug_format('[apply_mappings3] Applying START effects ~w to ~w\n', [Effects, State]),
  apply_effects(Effects, State, CurrentState),
  debug_format('[apply_mappings3] Current State after START effects: ~w\n', [CurrentState]),
  mapping(NewAction, Mappings),
  Pre  = '',
  apply_action_map(Mappings, CurrentState, TempPlan, NewState, NewPlan, Pre),
  % NewState = CurrentState,
  % NewPlan = TempPlan,
  apply_mappings(NewState, T_HL_Actions, NewPlan, RetPlan).
  % apply_mappings(CurrentState, T_HL_Actions, TempPlan, RetPlan).

apply_mappings(end, State, _NewAction, _EffectsStart, Effects, T_HL_Actions, TempPlan, RetPlan) :-
  debug_format('[apply_mappings3] Applying END effects ~w to ~w\n', [Effects, State]),
  apply_effects(Effects, State, CurrentState),
  debug_format('[apply_mappings3] Current State after END effects: ~w\n', [CurrentState]),
  apply_mappings(CurrentState, T_HL_Actions, TempPlan, RetPlan).

apply_mappings(_, _, _, _, _) :-
  % format('[apply_mappings5] Could not apply mappings\n'),
  fail.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Normalize one HL plan step to:
% - StepLabel: the term to store in the generated LL plan
% - Timing: start/end
% - HL_Action: action term used by hl_d_action/7 and mapping/2
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
normalize_hl_step(_ID-HL_Step, StepLabel, Timing, HL_Action) :-
  !,
  normalize_hl_step(HL_Step, StepLabel, Timing, HL_Action).

normalize_hl_step(start(HL_Action), start(HL_Action), start, HL_Action) :-
  !.

normalize_hl_step(end(HL_Action), end(HL_Action), end, HL_Action) :-
  !.

normalize_hl_step(HL_Step, HL_Step, Timing, HL_Action) :-
  HL_Step =.. [ActionName|AllArgs],
  AllArgs = [Timing|Args],
  (Timing = start ; Timing = end),
  HL_Action =.. [ActionName|Args].


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% This function applies the mappings of an action. It also checks that the ll action is applicable 
%and changes the state accordingly 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
apply_action_map([], State, Plan, State, Plan, _) :-
  debug_format('I get here').

apply_action_map([HAction|TActions], State, Plan, RetState, RetPlan, Pre) :-
  ll_d_action(HAction, PreconditionsStart, PreconditionsEnd, _Overall, EffectsStart, EffectsEnd, _Duration),

  % Check that the preconditions at start are met:
  (
    apply_action_map_single_ll(start, HAction, PreconditionsStart, EffectsStart, Plan, State, StartPlan, StartState, Pre)
    ->(
      apply_action_map_single_ll(end, HAction, PreconditionsEnd, EffectsEnd, StartPlan, StartState, TmpPlan, TmpState, Pre)
      ->(
        debug_format('~w[apply_action_map] Successfully applied ll action ~w\n', [Pre, HAction]),
        debug_format('~w[apply_action_map] New State: ~w\n', [Pre, TmpState]),
        debug_format('~w[apply_action_map] New Plan: ~w\n', [Pre, TmpPlan]),
        debug_format('~w[apply_action_map] Continuing with next actions ~w\n', [Pre, TActions]),
        % trace,
        apply_action_map(TActions, TmpState, TmpPlan, RetState, RetPlan, Pre)
      );(
        fail_msg('~w[apply_action_map] Could not apply end effects ~w after applying start effects ~w in state ~w\n', [Pre, EffectsEnd, EffectsStart, State]),
        fail
      )
    );(
      fail_msg('~w[apply_action_map] Could not apply start effects ~w in state ~w\n', [Pre, EffectsStart, State]),
      fail
    )
  ),
  true.

apply_action_map([HAction|_TActions], _State, [LastAction|_TPlan], _RetState, _RetPlan, Pre) :-
  \+ ll_d_action(HAction, _PreconditionsStart, _PreconditionsEnd, _Overall, _EffectsStart, _EffectsEnd, _Duration),
  fail_msg('~w[apply_action_map] Could not find ll action ~w to apply mapping after ~w\n', [Pre, HAction, LastAction]),
  fail.

apply_action_map(List, _, _, _, _, _) :-
  fail_msg('[apply_action_map] Could not apply action map ~w\n', [List]),
  fail.




apply_action_map_single_ll(Phase, HAction, Preconditions, Effects, Plan, State, RetPlan, RetState, Pre) :-
  % Check that the preconditions at start are met:
  (
    verify_preconditions(State, Preconditions)
    % If they are, change the state and continue with the end preconditions - effects
    ->(
      length(Plan, Length),
      format(atom(NewPre), '\t~w', [Pre]),
      LLStep =.. [Phase, HAction],
      append([Length-LLStep], Plan, RetPlan),
      debug_format('~w[apply_action_map] Updated Plan after adding ~w: ~w\n', [NewPre, LLStep, RetPlan]),
      apply_effects(Effects, State, RetState),
      debug_format('~w[apply_action_map] State changed to ~w\n', [NewPre, RetState])
    );(
      fail_msg('~w[apply_action_map] Preconditions ~w not met in state ~w\n', [Pre, Preconditions, State]),
      fail
    )
  ),
  true.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
