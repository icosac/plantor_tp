:- ensure_loaded('../src/utility.pl').

:- dynamic checked_kb_file/1.

% Run the full consistency suite for one KB file, covering both high-level and
% low-level action layers when both are present.
% Example: check_kb_consistency('../../kb/crane.pl') checks HL actions,
% LL actions, their shared state predicates, and mappings.
check_kb_consistency(KBFilePath) :-
    with_checked_kb_file(KBFilePath, check_kb_consistency_for(all)),
    succ_msg('ALL IS IN ORDER').
check_kb_consistency(_KBFilePath) :-
    fatal_msg('ERROR IN THE KB').

% Run only the high-level part of the consistency suite for one KB file.
% Example: check_hl_kb_consistency('../../kb/crane.pl') checks hl_d_action/7
% definitions and ignores ll_* predicates and mappings.
check_hl_kb_consistency(KBFilePath) :-
    with_checked_kb_file(KBFilePath, check_kb_consistency_for(hl)),
    succ_msg('HIGH-LEVEL KB IS IN ORDER').
check_hl_kb_consistency(_KBFilePath) :-
    fatal_msg('ERROR IN THE HIGH-LEVEL KB').

% Run only the low-level part of the consistency suite for one KB file.
% Example: check_ll_kb_consistency('../../kb/crane.pl') checks ll_d_action/7
% definitions and low-level state predicates.
check_ll_kb_consistency(KBFilePath) :-
    with_checked_kb_file(KBFilePath, check_kb_consistency_for(ll)),
    succ_msg('LOW-LEVEL KB IS IN ORDER').
check_ll_kb_consistency(_KBFilePath) :-
    fatal_msg('ERROR IN THE LOW-LEVEL KB').

check_kb_consistency :-
    fatal_msg('Please call check_kb_consistency(KBFilePath).').

check_hl_kb_consistency :-
    fatal_msg('Please call check_hl_kb_consistency(KBFilePath).').

check_ll_kb_consistency :-
    fatal_msg('Please call check_ll_kb_consistency(KBFilePath).').

% Dispatch the concrete consistency checks for a layer:
% - all: HL and LL actions, plus mappings.
% - hl: only non-ll_* signatures and high-level actions.
% - ll: only ll_* signatures and low-level actions.
check_kb_consistency_for(Kind) :-
    run_named_checks(
        'consistency_checks',
        [
            check('satisfy_preconditions', satisfy_preconditions_for(Kind)),
            check('effects_consistency', effects_consistency_for(Kind)),
            check('closed_world_coverage', closed_world_coverage_for(Kind)),
            check('kb_vs_states_separation_check', kb_vs_states_separation_check_for(Kind)),
            check('static_vs_dynamic_check', static_vs_dynamic_check_for(Kind)),
            check('abstraction_layer_consistency', abstraction_layer_consistency_for(Kind)),
            check('mappings_consistency', mappings_consistency_for(Kind))
        ]
    ).


% Check that each action precondition list is internally satisfiable.
% A single start/end/overall precondition list must not require a literal and
% its negation at the same time.
% Example: [at(r1, room1), neg(at(r1, room1))] fails, while having the same
% literal in different phases is not checked here.
satisfy_preconditions :-
    satisfy_preconditions_for(all).

satisfy_preconditions_for(Kind) :-
    \+ has_actions(Kind), !.
satisfy_preconditions_for(Kind) :-
    forall(
        action_instance(Kind, _Name, PreconditionsStart, PreconditionsEnd, Overall, _EffectsStart, _EffectsEnd, _Duration),
        (
            satisfy_preconditions(PreconditionsStart),
            satisfy_preconditions(PreconditionsEnd),
            satisfy_preconditions(Overall)
        )
    ).

satisfy_preconditions([]).
satisfy_preconditions([Precondition|Tail]) :-
    \+ opposite_precondition_in_list(Precondition, Tail),
    satisfy_preconditions(Tail).

opposite_precondition_in_list(neg(Precondition), Preconditions) :-
    member(OtherPrecondition, Preconditions),
    OtherPrecondition == Precondition.
opposite_precondition_in_list(Precondition, Preconditions) :-
    Precondition \= neg(_),
    member(neg(OtherPrecondition), Preconditions),
    OtherPrecondition == Precondition.



% Group of checks for action effects and action predicate declarations:
% - An effect list cannot add and delete the same unifiable literal.
% - Every predicate used in a precondition or effect must appear in the domain
%   signature inferred from init/goal/effects/static KB facts.
% - Static KB predicates, except ignored ones, must be used by the model.
% Example: [add(loaded(c1)), del(loaded(c1))] in one effect phase fails.
effects_consistency :-
    effects_consistency_for(all).

effects_consistency_for(Kind) :-
    run_named_checks(
        'effects_consistency',
        [
            check('effects_no_opposites', effects_no_opposites_for(Kind)),
            check('durative_lifecycle_consistency', durative_lifecycle_consistency_for(Kind)),
            check('effects_preconditions_defined', effects_preconditions_defined_for(Kind)),
            check('effects_no_unused_static_predicates', effects_no_unused_static_predicates_for(Kind))
        ]
    ).



% Check closed-world reachability of state predicate signatures.
% The planner assumes the KB lists all relevant state-changing facts, so this
% catches predicates that cannot become useful or true under the declared
% actions.
% Examples:
% - goal_state([delivered(pkg1)]) fails if delivered/1 is neither initially
%   true nor added by any action.
% - del(loaded(pkg1)) fails if no action ever add(loaded(_)).
closed_world_coverage :-
    closed_world_coverage_for(all).

closed_world_coverage_for(Kind) :-
    run_named_checks(
        'closed_world_coverage',
        [
            check('goal_predicates_produced_or_initial', goal_predicates_produced_or_initial_for(Kind)),
            check('deleted_predicates_reintroduced', deleted_predicates_reintroduced_for(Kind)),
            check('added_predicates_required', added_predicates_required_for(Kind)),
            check('precondition_predicates_reachable', precondition_predicates_reachable_for(Kind))
        ]
    ).



% Check that action effects do not change static KB predicates.
% Static predicates are ordinary facts in the KB, excluding init_state/1,
% goal_state/1, action declarations, mappings, and similar metadata.
% Example: if agent(r1). is a static fact, then add(agent(r2)) or del(agent(r1))
% in an action effect fails because agent/1 is not a state predicate.
static_vs_dynamic_check :-
    static_vs_dynamic_check_for(all).

static_vs_dynamic_check_for(Kind) :-
    layer_static_fact_signatures(Kind, StaticSignatures),
    layer_effect_signatures(Kind, EffectSignatures),
    signatures_intersection(StaticSignatures, EffectSignatures, Violations),
    (
        Violations = []
        -> true
        ;  format('[static_vs_dynamic_check] Static predicates changed by effects: ~w~n', [Violations]),
           fail
    ).


% Check that static KB predicates are not reused as state predicates.
% A predicate signature must appear either as general KB knowledge or in
% init_state/1 and goal_state/1, not both.
% Example: agent(r1). together with init_state([agent(r1)]) fails because
% agent/1 is both static knowledge and part of the state.
kb_vs_states_separation_check :-
    kb_vs_states_separation_check_for(all).

kb_vs_states_separation_check_for(Kind) :-
    layer_static_fact_signatures(Kind, StaticSignatures),
    layer_init_signatures(Kind, InitSignatures),
    layer_goal_signatures(Kind, GoalSignatures),
    append(InitSignatures, GoalSignatures, StateSignaturesTmp),
    sort(StateSignaturesTmp, StateSignatures),
    signatures_intersection(StaticSignatures, StateSignatures, Overlap),
    (
        Overlap = []
        -> true
        ;  format('[kb_vs_states_separation_check] Predicates used both in KB and states: ~w~n', [Overlap]),
           fail
    ).


% Check that high-level and low-level action layers do not leak into each other.
% High-level action literals must not use ll_* predicate signatures. Low-level
% action effects must only modify ll_* predicate signatures.
% Example: hl_d_action(..., [ll_at(r1, p1)], ...) fails; ll_d_action with
% add(at(r1, room1)) fails because at/2 is not low-level.
abstraction_layer_consistency :-
    abstraction_layer_consistency_for(all).

abstraction_layer_consistency_for(hl) :-
    hl_actions_no_low_level_literals.
abstraction_layer_consistency_for(ll) :-
    ll_actions_only_modify_low_level_literals.
abstraction_layer_consistency_for(all) :-
    run_named_checks(
        'abstraction_layer_consistency',
        [
            check('hl_actions_no_low_level_literals', hl_actions_no_low_level_literals),
            check('ll_actions_only_modify_low_level_literals', ll_actions_only_modify_low_level_literals)
        ]
    ).


% Check that HL-to-LL mappings refer to declared actions and feasible durations.
% Mapping heads must unify with declared HL actions; mapped elements must unify
% with declared LL actions; and the HL duration interval must contain the sum of
% the mapped LL duration intervals.
% Example: mapping(move(a,b), [ll_drive(a,b)]) fails if move/2 is not an
% hl_d_action/7 or if ll_drive/2 is not an ll_d_action/7.
mappings_consistency :-
    mappings_consistency_for(all).

mappings_consistency_for(hl) :-
    !.
mappings_consistency_for(_Kind) :-
    run_named_checks(
        'mappings_consistency',
        [
            check('mappings_reference_existing_hl_actions', mappings_reference_existing_hl_actions),
            check('mappings_reference_existing_ll_actions', mappings_reference_existing_ll_actions),
            check('mappings_duration_bounds_cover_ll_sums', mappings_duration_bounds_cover_ll_sums)
        ]
    ).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%                                   HELPERS                                  %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

run_named_checks(Label, Checks) :-
    findall(
        Name,
        (
            member(check(Name, Goal), Checks),
            \+ once(Goal)
        ),
        Failed
    ),
    (
        Failed = []
        -> true
        ;  format('[~w] Failed checks: ~w~n', [Label, Failed]),
           fail
    ).

% Check that no single start/end effect list contains both add(Literal) and
% del(Literal) for literals that can denote the same state fact under the
% action's declared constraints.
% Example: [add(at(r1, room1)), del(at(r1, room1))] fails for that action phase.
effects_no_opposites :-
    effects_no_opposites_for(all).

effects_no_opposites_for(Kind) :-
    findall(
        issue(ActionName, Phase, Literal),
        (
            action_instance(Kind, ActionName, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, _Duration),
            member(phase(Phase, Effects), [phase(start, EffectsStart), phase(end, EffectsEnd)]),
            member(add(AddLiteral), Effects),
            member(del(DelLiteral), Effects),
            append(PreconditionsStart, PreconditionsEnd, TmpPreconditions),
            append(TmpPreconditions, Overall, Preconditions),
            same_phase_effects_conflict(AddLiteral, DelLiteral, Preconditions),
            Literal = AddLiteral
        ),
        Issues
    ),
    sort(Issues, UniqueIssues),
    (
        UniqueIssues = []
        -> true
        ;  format('[effects_consistency] Opposite add/del effects in same effect set: ~w~n', [UniqueIssues]),
           fail
    ).

same_phase_effects_conflict(AddLiteral, DelLiteral, Preconditions) :-
    copy_term((AddLiteral, DelLiteral, Preconditions), (CopiedAdd, CopiedDel, CopiedPreconditions)),
    CopiedAdd = CopiedDel,
    \+ forced_disequality_violation(CopiedPreconditions).

forced_disequality_violation(Preconditions) :-
    member(Precondition, Preconditions),
    disequality_precondition(Precondition, Left, Right),
    Left == Right.

disequality_precondition((Left \= Right), Left, Right).
disequality_precondition(dif(Left, Right), Left, Right).

% Check that an action does not invalidate its own end preconditions or overall
% invariants at start. End preconditions are tested before end effects are
% applied, and overall invariants are enforced after start effects are applied,
% so a start effect that deletes a positive lifecycle condition, or adds a
% negated lifecycle condition, makes that durative action impossible.
% Examples:
% - PreEnd=[clear(b)], EffStart=[del(clear(b))] fails.
% - Overall=[at(b, p)], EffStart=[del(at(b, p))] fails.
durative_lifecycle_consistency :-
    durative_lifecycle_consistency_for(all).

durative_lifecycle_consistency_for(Kind) :-
    findall(
        Issue,
        durative_lifecycle_issue_for(Kind, Issue),
        Issues
    ),
    sort(Issues, UniqueIssues),
    (
        UniqueIssues = []
        -> true
        ;  format('[effects_consistency] Start effects invalidate lifecycle conditions: ~w~n', [UniqueIssues]),
           fail
    ).

durative_lifecycle_issue_for(Kind, issue(ActionName, start_effect_conflicts_with_lifecycle_condition(Effect, LifecycleCondition))) :-
    action_instance(Kind, ActionName, _PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, _EffectsEnd, _Duration),
    append(PreconditionsEnd, Overall, LifecycleConditions),
    member(LifecycleCondition, LifecycleConditions),
    member(Effect, EffectsStart),
    start_effect_violates_end_precondition(Effect, LifecycleCondition).

start_effect_violates_end_precondition(del(DeletedLiteral), EndPrecondition) :-
    EndPrecondition \= neg(_),
    precondition_domain_literal(EndPrecondition, RequiredLiteral),
    DeletedLiteral == RequiredLiteral.
start_effect_violates_end_precondition(add(AddedLiteral), neg(NegatedEndPrecondition)) :-
    expression_domain_literal(NegatedEndPrecondition, ForbiddenLiteral),
    AddedLiteral == ForbiddenLiteral.

% Check that every predicate signature used in action preconditions or effects
% is part of the inferred domain signature.
% Example: a precondition carrying(pkg1) fails if carrying/1 never appears in
% init_state/1, goal_state/1, any effect, or static KB facts.
effects_preconditions_defined :-
    effects_preconditions_defined_for(all).

effects_preconditions_defined_for(Kind) :-
    domain_signatures_for(Kind, DomainSignatures),
    used_precondition_or_effect_signatures_for(Kind, UsedSignatures),
    subtract(UsedSignatures, DomainSignatures, Undefined),
    (
        Undefined = []
        -> true
        ;  format('[effects_consistency] Predicates used but not in domain signature: ~w~n', [Undefined]),
           fail
    ).

% Check that static KB predicate signatures are used somewhere in the model,
% excluding signatures explicitly ignored by ignored_unused_static_signature/1.
% Example: robot(r1). fails as unused if robot/1 is never referenced by the
% init state, goal state, preconditions, or effects.
effects_no_unused_static_predicates :-
    effects_no_unused_static_predicates_for(all).

effects_no_unused_static_predicates_for(Kind) :-
    layer_static_fact_signatures(Kind, StaticSignatures),
    filter_unused_static_candidates(StaticSignatures, StaticCandidates),
    layer_used_model_signatures(Kind, UsedSignatures),
    subtract(StaticCandidates, UsedSignatures, Unused),
    (
        Unused = []
        -> true
        ;  format('[effects_consistency] Unused static predicates: ~w~n', [Unused]),
           fail
    ).

% Check that each goal predicate signature is either true in the initial state
% or can be produced by at least one action add effect.
% Example: goal_state([delivered(pkg1)]) fails if delivered/1 is not present in
% init_state/1 and no action has add(delivered(_)).
goal_predicates_produced_or_initial :-
    goal_predicates_produced_or_initial_for(all).

goal_predicates_produced_or_initial_for(Kind) :-
    layer_goal_signatures(Kind, GoalSignatures),
    layer_init_signatures(Kind, InitSignatures),
    layer_added_effect_signatures(Kind, AddedSignatures),
    append(InitSignatures, AddedSignatures, ReachableSignatures),
    sort(ReachableSignatures, Reachable),
    subtract(GoalSignatures, Reachable, Missing),
    (
        Missing = []
        -> true
        ;  format('[closed_world_coverage] Goal predicates never produced (and not initially true): ~w~n', [Missing]),
           fail
    ).

% Check that every predicate signature deleted by an action can also be added by
% some action.
% Example: del(loaded(pkg1)) fails if no action has add(loaded(_)).
deleted_predicates_reintroduced :-
    deleted_predicates_reintroduced_for(all).

deleted_predicates_reintroduced_for(Kind) :-
    layer_deleted_effect_signatures(Kind, DeletedSignatures),
    layer_added_effect_signatures(Kind, AddedSignatures),
    subtract(DeletedSignatures, AddedSignatures, MissingAdds),
    (
        MissingAdds = []
        -> true
        ;  format('[closed_world_coverage] Predicates deleted but never added: ~w~n', [MissingAdds]),
           fail
    ).

% Check that every predicate signature added by an action is required somewhere,
% either by a goal or by an action precondition.
% Example: add(tmp_marker(x)) fails if tmp_marker/1 never appears in a goal or
% precondition.
added_predicates_required :-
    added_predicates_required_for(all).

added_predicates_required_for(Kind) :-
    layer_added_effect_signatures(Kind, AddedSignatures),
    layer_required_signatures(Kind, RequiredSignatures),
    subtract(AddedSignatures, RequiredSignatures, UnrequiredAdds),
    (
        UnrequiredAdds = []
        -> true
        ;  format('[closed_world_coverage] Predicates added but never required: ~w~n', [UnrequiredAdds]),
           fail
    ).

% Check that every predicate signature used in preconditions is reachable from
% the initial/static facts by repeatedly applying actions whose positive
% precondition signatures are already reachable.
% Example: a precondition loaded(pkg1) fails if loaded/1 is not initially/static
% and no chain of applicable action signatures can add loaded/1.
precondition_predicates_reachable :-
    precondition_predicates_reachable_for(all).

precondition_predicates_reachable_for(Kind) :-
    layer_precondition_signatures(Kind, PreconditionSignatures),
    reachable_state_signatures_for(Kind, ReachableSignatures),
    subtract(PreconditionSignatures, ReachableSignatures, Missing),
    (
        Missing = []
        -> true
        ;  format('[closed_world_coverage] Preconditions use unreachable predicates: ~w~n', [Missing]),
           fail
    ).

reachable_state_signatures_for(Kind, ReachableSignatures) :-
    layer_init_signatures(Kind, InitSignatures),
    static_fact_signatures(StaticSignatures),
    append(InitSignatures, StaticSignatures, SeedsTmp),
    sort(SeedsTmp, Seeds),
    saturate_reachable_signatures(Kind, Seeds, ReachableSignatures).

saturate_reachable_signatures(Kind, CurrentReachable, ReachableSignatures) :-
    findall(
        AddedSignature,
        (
            action_instance(Kind, _Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, _Duration),
            action_positive_precondition_signatures(PreconditionsStart, PreconditionsEnd, Overall, RequiredSignatures),
            signatures_subset(RequiredSignatures, CurrentReachable),
            action_added_effect_signatures(EffectsStart, EffectsEnd, AddedSignatures),
            member(AddedSignature, AddedSignatures)
        ),
        NewlyReachableTmp
    ),
    append(CurrentReachable, NewlyReachableTmp, NextReachableTmp),
    sort(NextReachableTmp, NextReachable),
    (
        NextReachable == CurrentReachable
        -> ReachableSignatures = CurrentReachable
        ;  saturate_reachable_signatures(Kind, NextReachable, ReachableSignatures)
    ).

action_positive_precondition_signatures(PreconditionsStart, PreconditionsEnd, Overall, Signatures) :-
    findall(
        Signature,
        (
            member(Preconditions, [PreconditionsStart, PreconditionsEnd, Overall]),
            member(Precondition, Preconditions),
            positive_precondition_domain_literal(Precondition, Literal),
            domain_literal(Literal),
            literal_signature(Literal, Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

positive_precondition_domain_literal(Precondition, Literal) :-
    Precondition \= neg(_),
    precondition_domain_literal(Precondition, Literal).

action_added_effect_signatures(EffectsStart, EffectsEnd, Signatures) :-
    findall(
        Signature,
        (
            member(Effects, [EffectsStart, EffectsEnd]),
            member(add(Literal), Effects),
            domain_literal(Literal),
            literal_signature(Literal, Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

signatures_subset([], _Set).
signatures_subset([Signature|Tail], Set) :-
    member(Signature, Set),
    signatures_subset(Tail, Set).

domain_signatures(Signatures) :-
    domain_signatures_for(all, Signatures).

domain_signatures_for(Kind, Signatures) :-
    init_signatures(InitSignatures),
    goal_signatures(GoalSignatures),
    effect_signatures_for(Kind, EffectSignatures),
    static_fact_signatures(StaticSignatures),
    append(InitSignatures, GoalSignatures, Tmp1),
    append(Tmp1, EffectSignatures, Tmp2),
    append(Tmp2, StaticSignatures, Tmp3),
    sort(Tmp3, Signatures).

used_precondition_or_effect_signatures(Signatures) :-
    used_precondition_or_effect_signatures_for(all, Signatures).

used_precondition_or_effect_signatures_for(Kind, Signatures) :-
    precondition_signatures_for(Kind, PreconditionSignatures),
    effect_signatures_for(Kind, EffectSignatures),
    append(PreconditionSignatures, EffectSignatures, Tmp),
    sort(Tmp, Signatures).

used_model_signatures(Signatures) :-
    layer_used_model_signatures(all, Signatures).

layer_used_model_signatures(Kind, Signatures) :-
    layer_init_signatures(Kind, InitSignatures),
    layer_goal_signatures(Kind, GoalSignatures),
    layer_precondition_signatures(Kind, PreconditionSignatures),
    layer_effect_signatures(Kind, EffectSignatures),
    append(InitSignatures, GoalSignatures, Tmp1),
    append(Tmp1, PreconditionSignatures, Tmp2),
    append(Tmp2, EffectSignatures, Tmp3),
    sort(Tmp3, Signatures).

required_signatures(Signatures) :-
    layer_required_signatures(all, Signatures).

layer_required_signatures(Kind, Signatures) :-
    layer_goal_signatures(Kind, GoalSignatures),
    layer_precondition_signatures(Kind, PreconditionSignatures),
    append(GoalSignatures, PreconditionSignatures, Tmp),
    sort(Tmp, Signatures).

init_signatures(Signatures) :-
    findall(
        Signature,
        (
            init_state(InitState),
            member(Literal, InitState),
            domain_literal(Literal),
            literal_signature(Literal, Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

goal_signatures(Signatures) :-
    findall(
        Signature,
        (
            goal_state(GoalState),
            member(Literal, GoalState),
            domain_literal(Literal),
            literal_signature(Literal, Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

precondition_signatures(Signatures) :-
    precondition_signatures_for(all, Signatures).

precondition_signatures_for(Kind, Signatures) :-
    findall(
        Signature,
        (
            action_preconditions_for(Kind, Preconditions),
            member(Precondition, Preconditions),
            precondition_domain_literal(Precondition, Literal),
            domain_literal(Literal),
            literal_signature(Literal, Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

effect_signatures(Signatures) :-
    effect_signatures_for(all, Signatures).

effect_signatures_for(Kind, Signatures) :-
    findall(
        Signature,
        (
            action_effects_for(Kind, _ActionName, _Phase, Effects),
            member(Effect, Effects),
            effect_literal(Effect, Literal),
            domain_literal(Literal),
            literal_signature(Literal, Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

added_effect_signatures(Signatures) :-
    added_effect_signatures_for(all, Signatures).

added_effect_signatures_for(Kind, Signatures) :-
    findall(
        Signature,
        (
            action_effects_for(Kind, _ActionName, _Phase, Effects),
            member(add(Literal), Effects),
            domain_literal(Literal),
            literal_signature(Literal, Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

deleted_effect_signatures(Signatures) :-
    deleted_effect_signatures_for(all, Signatures).

deleted_effect_signatures_for(Kind, Signatures) :-
    findall(
        Signature,
        (
            action_effects_for(Kind, _ActionName, _Phase, Effects),
            member(del(Literal), Effects),
            domain_literal(Literal),
            literal_signature(Literal, Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

layer_init_signatures(Kind, Signatures) :-
    init_signatures(InitSignatures),
    filter_signatures_by_kind(Kind, InitSignatures, Signatures).

layer_goal_signatures(Kind, Signatures) :-
    goal_signatures(GoalSignatures),
    filter_signatures_by_kind(Kind, GoalSignatures, Signatures).

layer_precondition_signatures(Kind, Signatures) :-
    precondition_signatures_for(Kind, RawSignatures),
    filter_signatures_by_kind(Kind, RawSignatures, Signatures).

layer_effect_signatures(Kind, Signatures) :-
    effect_signatures_for(Kind, RawSignatures),
    filter_signatures_by_kind(Kind, RawSignatures, Signatures).

layer_added_effect_signatures(Kind, Signatures) :-
    added_effect_signatures_for(Kind, RawSignatures),
    filter_signatures_by_kind(Kind, RawSignatures, Signatures).

layer_deleted_effect_signatures(Kind, Signatures) :-
    deleted_effect_signatures_for(Kind, RawSignatures),
    filter_signatures_by_kind(Kind, RawSignatures, Signatures).

static_fact_signatures(Signatures) :-
    findall(
        Signature,
        (
            kb_clause_head(Head),
            head_in_checked_kb(Head),
            literal_signature(Head, Signature),
            \+excluded_kb_head_signature(Signature)
        ),
        SignaturesTmp
    ),
    sort(SignaturesTmp, Signatures).

layer_static_fact_signatures(Kind, Signatures) :-
    static_fact_signatures(RawSignatures),
    filter_signatures_by_kind(Kind, RawSignatures, Signatures).

excluded_kb_head_signature(init_state/1).
excluded_kb_head_signature(goal_state/1).
excluded_kb_head_signature(ll_init/1).
excluded_kb_head_signature(hl_d_action/7).
excluded_kb_head_signature(ll_d_action/7).
excluded_kb_head_signature(mapping/2).
excluded_kb_head_signature(message/0).

kb_clause_head(Head) :-
    current_predicate(Name/Arity),
    functor(Head, Name, Arity),
    \+predicate_property(Head, built_in),
    clause(Head, _Body).

action_preconditions(Preconditions) :-
    action_preconditions_for(all, Preconditions).

action_preconditions_for(all, Preconditions) :-
    has_actions(hl),
    action_preconditions_for(hl, Preconditions).
action_preconditions_for(all, Preconditions) :-
    has_actions(ll),
    action_preconditions_for(ll, Preconditions).
action_preconditions_for(hl, Preconditions) :-
    current_predicate(hl_d_action/7),
    hl_d_action(Name, Preconditions, PreEnd, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(Name, Preconditions, PreEnd, Overall, EffStart, EffEnd, Duration)).
action_preconditions_for(hl, Preconditions) :-
    current_predicate(hl_d_action/7),
    hl_d_action(Name, PreStart, Preconditions, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(Name, PreStart, Preconditions, Overall, EffStart, EffEnd, Duration)).
action_preconditions_for(hl, Preconditions) :-
    current_predicate(hl_d_action/7),
    hl_d_action(Name, PreStart, PreEnd, Preconditions, EffStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(Name, PreStart, PreEnd, Preconditions, EffStart, EffEnd, Duration)).
action_preconditions_for(ll, Preconditions) :-
    current_predicate(ll_d_action/7),
    ll_d_action(Name, Preconditions, PreEnd, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(ll_d_action(Name, Preconditions, PreEnd, Overall, EffStart, EffEnd, Duration)).
action_preconditions_for(ll, Preconditions) :-
    current_predicate(ll_d_action/7),
    ll_d_action(Name, PreStart, Preconditions, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(ll_d_action(Name, PreStart, Preconditions, Overall, EffStart, EffEnd, Duration)).
action_preconditions_for(ll, Preconditions) :-
    current_predicate(ll_d_action/7),
    ll_d_action(Name, PreStart, PreEnd, Preconditions, EffStart, EffEnd, Duration),
    head_in_checked_kb(ll_d_action(Name, PreStart, PreEnd, Preconditions, EffStart, EffEnd, Duration)).

action_effects(Name, start, EffectsStart) :-
    action_effects_for(all, Name, start, EffectsStart).
action_effects(Name, end, EffectsEnd) :-
    action_effects_for(all, Name, end, EffectsEnd).

action_effects_for(all, Name, Phase, Effects) :-
    has_actions(hl),
    action_effects_for(hl, Name, Phase, Effects).
action_effects_for(all, Name, Phase, Effects) :-
    has_actions(ll),
    action_effects_for(ll, Name, Phase, Effects).
action_effects_for(hl, Name, start, EffectsStart) :-
    current_predicate(hl_d_action/7),
    hl_d_action(Name, PreStart, PreEnd, Overall, EffectsStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(Name, PreStart, PreEnd, Overall, EffectsStart, EffEnd, Duration)).
action_effects_for(hl, Name, end, EffectsEnd) :-
    current_predicate(hl_d_action/7),
    hl_d_action(Name, PreStart, PreEnd, Overall, EffStart, EffectsEnd, Duration),
    head_in_checked_kb(hl_d_action(Name, PreStart, PreEnd, Overall, EffStart, EffectsEnd, Duration)).
action_effects_for(ll, Name, start, EffectsStart) :-
    current_predicate(ll_d_action/7),
    ll_d_action(Name, PreStart, PreEnd, Overall, EffectsStart, EffEnd, Duration),
    head_in_checked_kb(ll_d_action(Name, PreStart, PreEnd, Overall, EffectsStart, EffEnd, Duration)).
action_effects_for(ll, Name, end, EffectsEnd) :-
    current_predicate(ll_d_action/7),
    ll_d_action(Name, PreStart, PreEnd, Overall, EffStart, EffectsEnd, Duration),
    head_in_checked_kb(ll_d_action(Name, PreStart, PreEnd, Overall, EffStart, EffectsEnd, Duration)).

% Check that HL actions do not mention low-level predicates in preconditions,
% overall conditions, or effects. Low-level predicates are recognized by the
% ll_ prefix in their predicate name.
% Example: a high-level precondition ll_at(robot1, wp1) fails because ll_at/2
% belongs to the low-level layer.
hl_actions_no_low_level_literals :-
    \+ has_checked_kb_predicate(hl_d_action/7), !.
hl_actions_no_low_level_literals :-
    findall(
        issue(ActionName, Part, Signature),
        (
            hl_action_literal(ActionName, Part, Literal),
            literal_signature(Literal, Signature),
            low_level_signature(Signature)
        ),
        Issues
    ),
    sort(Issues, UniqueIssues),
    (
        UniqueIssues = []
        -> true
        ;  format('[abstraction_layer_consistency] High-level actions contain low-level predicates: ~w~n', [UniqueIssues]),
           fail
    ).

% Check that LL action effects modify only low-level predicates.
% This check applies to effects only; LL preconditions may still read shared or
% high-level/static predicates if the KB uses them for grounding.
% Example: add(at(robot1, room1)) in an ll_d_action/7 fails, while
% add(ll_at(robot1, wp1)) is accepted.
ll_actions_only_modify_low_level_literals :-
    \+ has_checked_kb_predicate(ll_d_action/7), !.
ll_actions_only_modify_low_level_literals :-
    findall(
        issue(ActionName, Part, Signature),
        (
            ll_action_effect_literal(ActionName, Part, Literal),
            literal_signature(Literal, Signature),
            \+ low_level_signature(Signature)
        ),
        Issues
    ),
    sort(Issues, UniqueIssues),
    (
        UniqueIssues = []
        -> true
        ;  format('[abstraction_layer_consistency] Low-level actions modify non-low-level predicates: ~w~n', [UniqueIssues]),
           fail
    ).

% Check that every mapping head corresponds to an existing HL action
% declaration, using unification rather than exact textual equality.
% Example: mapping(deliver(p1), [...]) fails if no hl_d_action/7 has a name
% that can unify with deliver(p1).
mappings_reference_existing_hl_actions :-
    \+ has_checked_kb_predicate(mapping/2), !.
mappings_reference_existing_hl_actions :-
    findall(
        issue(HLAction),
        (
            mapping(HLAction, LLActions),
            head_in_checked_kb(mapping(HLAction, LLActions)),
            \+ declared_hl_action(HLAction)
        ),
        Issues
    ),
    sort(Issues, UniqueIssues),
    (
        UniqueIssues = []
        -> true
        ;  format('[mappings_consistency] Mapping heads not declared as high-level actions: ~w~n', [UniqueIssues]),
           fail
    ).

% Check that every LL action listed in every mapping corresponds to an existing
% LL action declaration, using unification.
% Example: mapping(deliver(P), [ll_pick(P), ll_drop(P)]) fails if ll_drop/1 is
% not declared as an ll_d_action/7.
mappings_reference_existing_ll_actions :-
    \+ has_checked_kb_predicate(mapping/2), !.
mappings_reference_existing_ll_actions :-
    findall(
        issue(HLAction, LLAction),
        (
            mapping(HLAction, LLActions),
            head_in_checked_kb(mapping(HLAction, LLActions)),
            member(LLAction, LLActions),
            \+ declared_ll_action(LLAction)
        ),
        Issues
    ),
    sort(Issues, UniqueIssues),
    (
        UniqueIssues = []
        -> true
        ;  format('[mappings_consistency] Mapped actions not declared as low-level actions: ~w~n', [UniqueIssues]),
           fail
    ).

% Check that the duration interval of each mapped HL action covers the summed
% duration interval of its mapped LL action sequence.
% Example: an HL duration [2, 5] fails for mapped LL durations [1, 3] and
% [2, 4], because the LL maximum sum is 7.
mappings_duration_bounds_cover_ll_sums :-
    \+ has_checked_kb_predicate(mapping/2), !.
mappings_duration_bounds_cover_ll_sums :-
    findall(
        issue(HLAction, hl_bounds(HLMin, HLMax), ll_bounds_sum(LLMinSum, LLMaxSum)),
        (
            mapping(HLAction, LLActions),
            head_in_checked_kb(mapping(HLAction, LLActions)),
            mapping_duration_bounds(HLAction, LLActions, HLMin, HLMax, LLMinSum, LLMaxSum),
            (
                HLMin > LLMinSum
                ;
                HLMax < LLMaxSum
            )
        ),
        Issues
    ),
    sort(Issues, UniqueIssues),
    (
        UniqueIssues = []
        -> true
        ;  format('[mappings_consistency] High-level duration bounds do not enclose mapped low-level duration sums: ~w~n', [UniqueIssues]),
           fail
    ).

mapping_duration_bounds(HLAction, LLActions, HLMin, HLMax, LLMinSum, LLMaxSum) :-
    hl_action_duration_term(HLAction, HLDuration),
    consistency_duration_bounds(HLDuration, HLMin, HLMax),
    ll_actions_duration_sum_bounds(LLActions, LLMinSum, LLMaxSum).

hl_action_duration_term(Action, Duration) :-
    current_predicate(hl_d_action/7),
    hl_d_action(Action, PreStart, PreEnd, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(Action, PreStart, PreEnd, Overall, EffStart, EffEnd, Duration)),
    !.

ll_action_duration_term(Action, Duration) :-
    current_predicate(ll_d_action/7),
    ll_d_action(Action, PreStart, PreEnd, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(ll_d_action(Action, PreStart, PreEnd, Overall, EffStart, EffEnd, Duration)),
    !.

ll_actions_duration_sum_bounds([], 0, 0).
ll_actions_duration_sum_bounds([LLAction|Tail], TotalMin, TotalMax) :-
    ll_action_duration_term(LLAction, LLDuration),
    consistency_duration_bounds(LLDuration, LLMin, LLMax),
    ll_actions_duration_sum_bounds(Tail, TailMin, TailMax),
    TotalMin is LLMin + TailMin,
    TotalMax is LLMax + TailMax.

consistency_duration_bounds([Min, Max], Min, Max) :-
    number(Min),
    number(Max),
    !.
consistency_duration_bounds([Value], Value, Value) :-
    number(Value),
    !.
consistency_duration_bounds(Value, Value, Value) :-
    number(Value).

hl_action_literal(ActionName, pre_start, Literal) :-
    hl_d_action(ActionName, Preconditions, PreEnd, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(ActionName, Preconditions, PreEnd, Overall, EffStart, EffEnd, Duration)),
    member(Precondition, Preconditions),
    precondition_domain_literal(Precondition, Literal),
    domain_literal(Literal).
hl_action_literal(ActionName, pre_end, Literal) :-
    hl_d_action(ActionName, PreStart, Preconditions, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(ActionName, PreStart, Preconditions, Overall, EffStart, EffEnd, Duration)),
    member(Precondition, Preconditions),
    precondition_domain_literal(Precondition, Literal),
    domain_literal(Literal).
hl_action_literal(ActionName, overall, Literal) :-
    hl_d_action(ActionName, PreStart, PreEnd, Preconditions, EffStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(ActionName, PreStart, PreEnd, Preconditions, EffStart, EffEnd, Duration)),
    member(Precondition, Preconditions),
    precondition_domain_literal(Precondition, Literal),
    domain_literal(Literal).
hl_action_literal(ActionName, eff_start, Literal) :-
    hl_d_action(ActionName, PreStart, PreEnd, Overall, Effects, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(ActionName, PreStart, PreEnd, Overall, Effects, EffEnd, Duration)),
    member(Effect, Effects),
    effect_literal(Effect, Literal),
    domain_literal(Literal).
hl_action_literal(ActionName, eff_end, Literal) :-
    hl_d_action(ActionName, PreStart, PreEnd, Overall, EffStart, Effects, Duration),
    head_in_checked_kb(hl_d_action(ActionName, PreStart, PreEnd, Overall, EffStart, Effects, Duration)),
    member(Effect, Effects),
    effect_literal(Effect, Literal),
    domain_literal(Literal).

ll_action_effect_literal(ActionName, eff_start, Literal) :-
    ll_d_action(ActionName, PreStart, PreEnd, Overall, Effects, EffEnd, Duration),
    head_in_checked_kb(ll_d_action(ActionName, PreStart, PreEnd, Overall, Effects, EffEnd, Duration)),
    member(Effect, Effects),
    effect_literal(Effect, Literal),
    domain_literal(Literal).
ll_action_effect_literal(ActionName, eff_end, Literal) :-
    ll_d_action(ActionName, PreStart, PreEnd, Overall, EffStart, Effects, Duration),
    head_in_checked_kb(ll_d_action(ActionName, PreStart, PreEnd, Overall, EffStart, Effects, Duration)),
    member(Effect, Effects),
    effect_literal(Effect, Literal),
    domain_literal(Literal).

declared_hl_action(Action) :-
    current_predicate(hl_d_action/7),
    hl_d_action(DeclaredAction, PreStart, PreEnd, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(hl_d_action(DeclaredAction, PreStart, PreEnd, Overall, EffStart, EffEnd, Duration)),
    literals_can_unify(DeclaredAction, Action),
    !.

declared_ll_action(Action) :-
    current_predicate(ll_d_action/7),
    ll_d_action(DeclaredAction, PreStart, PreEnd, Overall, EffStart, EffEnd, Duration),
    head_in_checked_kb(ll_d_action(DeclaredAction, PreStart, PreEnd, Overall, EffStart, EffEnd, Duration)),
    literals_can_unify(DeclaredAction, Action),
    !.

low_level_signature(Name/_Arity) :-
    atom(Name),
    sub_atom(Name, 0, 3, _, 'll_').

with_checked_kb_file(KBFilePath, Goal) :-
    prepare_checked_kb_file(KBFilePath, KBAbsPath, WasPreviouslyLoaded),
    setup_call_cleanup(
        true,
        Goal,
        cleanup_checked_kb_file(KBAbsPath, WasPreviouslyLoaded)
    ).

prepare_checked_kb_file(KBFilePath, KBAbsPath, WasPreviouslyLoaded) :-
    absolute_file_name(KBFilePath, KBAbsPath, [file_errors(fail)]),
    (
        kb_file_loaded(KBAbsPath)
        -> WasPreviouslyLoaded = true
        ;  WasPreviouslyLoaded = false
    ),
    (
        WasPreviouslyLoaded = true
        -> true
        ;  ensure_loaded(KBAbsPath)
    ),
    retractall(checked_kb_file(_)),
    asserta(checked_kb_file(KBAbsPath)).

cleanup_checked_kb_file(KBAbsPath, WasPreviouslyLoaded) :-
    retractall(checked_kb_file(_)),
    (
        WasPreviouslyLoaded = true
        -> true
        ;  unload_file(KBAbsPath)
    ).

kb_file_loaded(KBAbsPath) :-
    source_file(_Head, KBAbsPath),
    !.

head_in_checked_kb(Head) :-
    checked_kb_file(KBFilePath),
    source_file(Head, SourceFilePath),
    absolute_file_name(SourceFilePath, SourceAbsPath, [file_errors(fail)]),
    KBFilePath == SourceAbsPath.

has_checked_kb_predicate(Name/Arity) :-
    current_predicate(Name/Arity),
    functor(Head, Name, Arity),
    head_in_checked_kb(Head),
    !.

has_actions(all) :-
    has_checked_kb_predicate(hl_d_action/7).
has_actions(all) :-
    has_checked_kb_predicate(ll_d_action/7).
has_actions(hl) :-
    has_checked_kb_predicate(hl_d_action/7).
has_actions(ll) :-
    has_checked_kb_predicate(ll_d_action/7).

action_instance(all, Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration) :-
    has_actions(hl),
    action_instance(hl, Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration).
action_instance(all, Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration) :-
    has_actions(ll),
    action_instance(ll, Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration).
action_instance(hl, Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration) :-
    current_predicate(hl_d_action/7),
    hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration),
    head_in_checked_kb(hl_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration)).
action_instance(ll, Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration) :-
    current_predicate(ll_d_action/7),
    ll_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration),
    head_in_checked_kb(ll_d_action(Name, PreconditionsStart, PreconditionsEnd, Overall, EffectsStart, EffectsEnd, Duration)).

signature_matches_kind(all, _Signature).
signature_matches_kind(ll, Signature) :-
    low_level_signature(Signature).
signature_matches_kind(hl, Signature) :-
    \+ low_level_signature(Signature).

filter_signatures_by_kind(_Kind, [], []).
filter_signatures_by_kind(Kind, [Signature|Tail], [Signature|FilteredTail]) :-
    signature_matches_kind(Kind, Signature), !,
    filter_signatures_by_kind(Kind, Tail, FilteredTail).
filter_signatures_by_kind(Kind, [_Signature|Tail], FilteredTail) :-
    filter_signatures_by_kind(Kind, Tail, FilteredTail).

ignored_unused_static_signature(resources/1).

filter_unused_static_candidates([], []).
filter_unused_static_candidates([Signature|Tail], FilteredTail) :-
    ignored_unused_static_signature(Signature), !,
    filter_unused_static_candidates(Tail, FilteredTail).
filter_unused_static_candidates([Signature|Tail], [Signature|FilteredTail]) :-
    filter_unused_static_candidates(Tail, FilteredTail).

precondition_literal(neg(Literal), Literal) :- !.
precondition_literal(Literal, Literal).

precondition_domain_literal(Precondition, Literal) :-
    precondition_literal(Precondition, PositivePrecondition),
    expression_domain_literal(PositivePrecondition, Literal).

expression_domain_literal((Left ; Right), Literal) :- !,
    (
        expression_domain_literal(Left, Literal)
        ;
        expression_domain_literal(Right, Literal)
    ).
expression_domain_literal((Left , Right), Literal) :- !,
    (
        expression_domain_literal(Left, Literal)
        ;
        expression_domain_literal(Right, Literal)
    ).
expression_domain_literal(Literal, Literal).

effect_literal(add(Literal), Literal).
effect_literal(del(Literal), Literal).

domain_literal(Literal) :-
    callable(Literal),
    \+predicate_property(Literal, built_in).

literal_signature(Literal, Name/Arity) :-
    functor(Literal, Name, Arity).

literals_can_unify(Left, Right) :-
    \+ \+ (Left = Right).

signatures_intersection(Signatures1, Signatures2, Intersection) :-
    findall(
        Signature,
        (
            member(Signature, Signatures1),
            member(Signature, Signatures2)
        ),
        IntersectionTmp
    ),
    sort(IntersectionTmp, Intersection).
