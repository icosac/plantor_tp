%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%                                  ENABLERS                                  %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

:- ensure_loaded('../src/utility.pl').


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Public API
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%! extract_enablers(+Plan, -Enablers)
% Given a (possibly indexed) mixed HL/LL plan, returns enabler edges:
%   enabler(FromID-FromStep, ToID-ToStep, Reason)
% where Reason is either:
% - causal(Literals): one or more literals connect effects of From to
%   preconditions of To
% - assumption(Tag): structural assumptions introduced for the current framework
extract_enablers(Plan, Enablers) :-
    normalize_plan(Plan, OrderedSteps),
    causal_enabler_edges(OrderedSteps, CausalEdges),
    assumption_enabler_edges(OrderedSteps, AssumptionEdges),
    projected_hl_boundary_edges(OrderedSteps, CausalEdges, ProjectedEdges),
    append([CausalEdges, AssumptionEdges, ProjectedEdges], AllEdges),
    sort(AllEdges, Enablers).

% Alias kept for readability at call sites.
enablers_from_plan(Plan, Enablers) :-
    extract_enablers(Plan, Enablers).

%! extract_start_end_links(+Plan, -Links)
% Given a (possibly indexed) mixed HL/LL plan, returns concrete start/end links:
%   start_end_link(StartID-start(Action), EndID-end(Action))
% Links are computed in plan order and disambiguate repeated action terms.
extract_start_end_links(Plan, Links) :-
    normalize_plan(Plan, OrderedSteps),
    start_end_links_from_steps(OrderedSteps, Links, _UnmatchedStarts, _UnmatchedEnds).

%! print_start_end_links(+Plan)
% Convenience wrapper: compute and print explicit start/end links.
print_start_end_links(Plan) :-
    extract_start_end_links(Plan, Links),
    print_start_end_links(Plan, Links).

%! print_start_end_links(+Plan, +Links)
% Prints explicit start/end links and reports unmatched boundaries.
print_start_end_links(Plan, Links) :-
    normalize_plan(Plan, OrderedSteps),
    start_end_links_from_steps(OrderedSteps, _ComputedLinks, UnmatchedStarts, UnmatchedEnds),
    format('[planner] Start/end links:~n'),
    (
        Links = []
        -> format('\t(none)~n')
        ;  forall(
               member(start_end_link(StartID-StartStep, EndID-EndStep), Links),
               format('\t~w-~w <-> ~w-~w~n', [StartID, StartStep, EndID, EndStep])
           )
    ),
    print_unmatched_start_steps(UnmatchedStarts),
    print_unmatched_end_steps(UnmatchedEnds).

%! print_plan_with_enablers(+Plan)
% Convenience wrapper: compute enablers and print plan steps with incoming
% enablers for each step.
print_plan_with_enablers(Plan) :-
    extract_enablers(Plan, Enablers),
    print_plan_with_enablers(Plan, Enablers).

%! print_plan_with_enablers(+Plan, +Enablers)
% Prints every step of the (possibly indexed) plan and the enablers that support
% that step.
print_plan_with_enablers(Plan, Enablers) :-
    normalize_plan(Plan, OrderedSteps),
    format('[enablers] Plan actions with enablers:~n'),
    forall(
        member(step(ID, Step), OrderedSteps),
        (
            incoming_enabler_ids_for_step(ID, Step, Enablers, IncomingIDs),
            format('\t~w-~w <= ~w~n', [ID, Step, IncomingIDs])
        )
    ).

%! print_plan_durations(+Plan)
% Prints duration bounds for each start/end step in the normalized plan.
print_plan_durations(Plan) :-
    normalize_plan(Plan, OrderedSteps),
    format('[planner] Duration constraints:~n'),
    forall(
        member(step(ID, Step), OrderedSteps),
        (
            step_duration_bounds(Step, Min, Max)
            -> format('\t~w-~w => [~w, ~w]~n', [ID, Step, Min, Max])
            ; true
        )
    ).

step_duration_bounds(start(Action), Min, Max) :-
    !,
    action_duration_bounds(Action, Min, Max).
step_duration_bounds(end(Action), Min, Max) :-
    !,
    action_duration_bounds(Action, Min, Max).

action_duration_bounds(Action, Min, Max) :-
    (
        hl_d_action(Action, _PreStart, _PreEnd, _Overall, _EffStart, _EffEnd, Duration)
        ;
        ll_d_action(Action, _PreStart, _PreEnd, _Overall, _EffStart, _EffEnd, Duration)
    ),
    duration_bounds(Duration, Min, Max),
    !.

duration_bounds([Min, Max], Min, Max) :- !.
duration_bounds([Value], Value, Value) :- !.
duration_bounds(Value, Value, Value) :-
    number(Value).

incoming_enabler_ids_for_step(TargetID, TargetStep, Enablers, IncomingIDs) :-
    findall(
        SourceID,
        member(enabler(SourceID-_, TargetID-TargetStep, _), Enablers),
        IncomingRaw
    ),
    sort(IncomingRaw, IncomingIDs).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Plan normalization helpers
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

normalize_plan(Plan, OrderedSteps) :-
    normalize_plan(Plan, 0, RawSteps),
    sort_steps_by_id(RawSteps, OrderedSteps).

normalize_plan([], _Index, []).
normalize_plan([H|T], Index, [step(ID, Step)|NormalizedTail]) :-
    (
        H = RawID-RawStep,
        number(RawID)
        -> ID = RawID, Step = RawStep
        ;  ID = Index, Step = H
    ),
    NextIndex is Index + 1,
    normalize_plan(T, NextIndex, NormalizedTail).

sort_steps_by_id(Steps, OrderedSteps) :-
    findall(
        ID-step(ID, Step),
        member(step(ID, Step), Steps),
        KeyedSteps
    ),
    keysort(KeyedSteps, OrderedKeyed),
    findall(
        StepTerm,
        member(_ID-StepTerm, OrderedKeyed),
        OrderedSteps
    ).

sort_start_end_links_by_start_id(Links, OrderedLinks) :-
    findall(
        StartID-start_end_link(StartID-StartStep, EndID-EndStep),
        member(start_end_link(StartID-StartStep, EndID-EndStep), Links),
        KeyedLinks
    ),
    keysort(KeyedLinks, OrderedKeyedLinks),
    findall(
        Link,
        member(_ID-Link, OrderedKeyedLinks),
        OrderedLinks
    ).

start_end_links_from_steps(OrderedSteps, Links, UnmatchedStarts, UnmatchedEnds) :-
    pair_start_end_steps(
        OrderedSteps,
        [],
        OpenStartsAfterScan,
        [],
        LinksReversed,
        [],
        UnmatchedEndsReversed
    ),
    reverse(LinksReversed, LinksTmp),
    sort_start_end_links_by_start_id(LinksTmp, Links),
    reverse(UnmatchedEndsReversed, UnmatchedEndsTmp),
    flatten_open_starts(OpenStartsAfterScan, UnmatchedStartsTmp),
    sort_steps_by_id(UnmatchedStartsTmp, UnmatchedStarts),
    sort_steps_by_id(UnmatchedEndsTmp, UnmatchedEnds).

pair_start_end_steps([], OpenStarts, OpenStarts, Links, Links, UnmatchedEnds, UnmatchedEnds).
pair_start_end_steps([step(ID, start(Action))|Tail], OpenStarts0, OpenStartsF, Links0, LinksF, UnmatchedEnds0, UnmatchedEndsF) :-
    !,
    push_open_start(Action, step(ID, start(Action)), OpenStarts0, OpenStarts1),
    pair_start_end_steps(Tail, OpenStarts1, OpenStartsF, Links0, LinksF, UnmatchedEnds0, UnmatchedEndsF).
pair_start_end_steps([step(ID, end(Action))|Tail], OpenStarts0, OpenStartsF, Links0, LinksF, UnmatchedEnds0, UnmatchedEndsF) :-
    !,
    (
        pop_open_start(Action, OpenStarts0, step(StartID, StartStep), OpenStarts1)
        -> pair_start_end_steps(
               Tail,
               OpenStarts1,
               OpenStartsF,
               [start_end_link(StartID-StartStep, ID-end(Action))|Links0],
               LinksF,
               UnmatchedEnds0,
               UnmatchedEndsF
           )
        ;  pair_start_end_steps(
               Tail,
               OpenStarts0,
               OpenStartsF,
               Links0,
               LinksF,
               [step(ID, end(Action))|UnmatchedEnds0],
               UnmatchedEndsF
           )
    ).
pair_start_end_steps([_Other|Tail], OpenStarts0, OpenStartsF, Links0, LinksF, UnmatchedEnds0, UnmatchedEndsF) :-
    pair_start_end_steps(Tail, OpenStarts0, OpenStartsF, Links0, LinksF, UnmatchedEnds0, UnmatchedEndsF).

push_open_start(Action, StartStep, [], [Action-[StartStep]]).
push_open_start(Action, StartStep, [Action-Stack|Tail], [Action-[StartStep|Stack]|Tail]) :-
    !.
push_open_start(Action, StartStep, [OtherAction-Stack|Tail], [OtherAction-Stack|TailUpdated]) :-
    push_open_start(Action, StartStep, Tail, TailUpdated).

pop_open_start(Action, [Action-[StartStep|RestStack]|Tail], StartStep, UpdatedOpenStarts) :-
    !,
    normalize_open_stack(Action, RestStack, Tail, UpdatedOpenStarts).
pop_open_start(Action, [OtherAction-Stack|Tail], StartStep, [OtherAction-Stack|TailUpdated]) :-
    pop_open_start(Action, Tail, StartStep, TailUpdated).

normalize_open_stack(_Action, [], Tail, Tail).
normalize_open_stack(Action, RestStack, Tail, [Action-RestStack|Tail]).

flatten_open_starts([], []).
flatten_open_starts([_Action-Starts|Tail], FlatStarts) :-
    flatten_open_starts(Tail, FlatTail),
    append(Starts, FlatTail, FlatStarts).

print_unmatched_start_steps([]).
print_unmatched_start_steps(UnmatchedStarts) :-
    format('[planner] WARNING: Unmatched start steps:~n'),
    forall(
        member(step(ID, Step), UnmatchedStarts),
        format('\t~w-~w~n', [ID, Step])
    ).

print_unmatched_end_steps([]).
print_unmatched_end_steps(UnmatchedEnds) :-
    format('[planner] WARNING: Unmatched end steps:~n'),
    forall(
        member(step(ID, Step), UnmatchedEnds),
        format('\t~w-~w~n', [ID, Step])
    ).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Causal enablers (effects -> preconditions)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

causal_enabler_edges([], []).
causal_enabler_edges([_], []).
causal_enabler_edges(OrderedSteps, Edges) :-
    findall(
        enabler(SourceID-SourceStep, TargetID-TargetStep, causal(MatchedLiterals)),
        (
            member(step(TargetID, TargetStep), OrderedSteps),
            action_step_preconditions(TargetStep, PositivePreconditions, NegativePreconditions),
            (PositivePreconditions \= [] ; NegativePreconditions \= []),
            member(step(SourceID, SourceStep), OrderedSteps),
            SourceID < TargetID,
            action_step_effects(SourceStep, Effects),
            Effects \= [],
            effect_matches_preconditions(Effects, PositivePreconditions, NegativePreconditions, MatchedLiterals)
        ),
        RawEdges
    ),
    sort(RawEdges, Edges).

action_step_preconditions(start(Action), Pos, Neg) :-
    action_definition(Action, PreStart, _PreEnd, Overall, _EffStart, _EffEnd),
    append(PreStart, Overall, Preconditions),
    split_preconditions(Preconditions, Pos, Neg).
action_step_preconditions(end(Action), Pos, Neg) :-
    action_definition(Action, _PreStart, PreEnd, Overall, _EffStart, _EffEnd),
    append(PreEnd, Overall, Preconditions),
    split_preconditions(Preconditions, Pos, Neg).
action_step_preconditions(_Step, [], []).

action_step_effects(start(Action), Effects) :-
    action_definition(Action, _PreStart, _PreEnd, _Overall, Effects, _EffEnd), !.
action_step_effects(end(Action), Effects) :-
    action_definition(Action, _PreStart, _PreEnd, _Overall, _EffStart, Effects), !.
action_step_effects(_Step, []).

action_definition(Action, PreStart, PreEnd, Overall, EffStart, EffEnd) :-
    hl_d_action(Action, PreStart, PreEnd, Overall, EffStart, EffEnd, _Duration), !.
action_definition(Action, PreStart, PreEnd, Overall, EffStart, EffEnd) :-
    ll_d_action(Action, PreStart, PreEnd, Overall, EffStart, EffEnd, _Duration).

split_preconditions(Preconditions, Positive, Negative) :-
    findall(
        Literal,
        (
            member(Precondition, Preconditions),
            positive_precondition_literal(Precondition, Literal)
        ),
        PosRaw
    ),
    sort(PosRaw, Positive),
    findall(
        Literal,
        (
            member(Precondition, Preconditions),
            negative_precondition_literal(Precondition, Literal)
        ),
        NegRaw
    ),
    sort(NegRaw, Negative).

positive_precondition_literal(Precondition, Literal) :-
    Precondition \= neg(_),
    enabler_domain_literal(Precondition),
    Literal = Precondition.

negative_precondition_literal(neg(Literal), Literal) :-
    enabler_domain_literal(Literal).

enabler_domain_literal(Literal) :-
    callable(Literal),
    \+ predicate_property(Literal, built_in).

effect_matches_preconditions(Effects, Positives, Negatives, MatchedLiterals) :-
    findall(
        Literal,
        (
            member(add(EffectLiteral), Effects),
            member(RequiredLiteral, Positives),
            enabler_literals_match(EffectLiteral, RequiredLiteral),
            Literal = EffectLiteral
        ),
        PosMatchesRaw
    ),
    findall(
        Literal,
        (
            member(del(EffectLiteral), Effects),
            member(RequiredLiteral, Negatives),
            enabler_literals_match(EffectLiteral, RequiredLiteral),
            Literal = EffectLiteral
        ),
        NegMatchesRaw
    ),
    append(PosMatchesRaw, NegMatchesRaw, MatchesRaw),
    sort(MatchesRaw, MatchedLiterals),
    MatchedLiterals \= [].

enabler_literals_match(Left, Right) :-
    \+ \+ (Left = Right).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Structural assumptions for the current framework
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

assumption_enabler_edges(OrderedSteps, Edges) :-
    hl_intervals(OrderedSteps, Intervals),
    assumption_edges_for_intervals(Intervals, IntervalEdges),
    ll_sequence_edges(Intervals, LLSequenceEdges),
    append(IntervalEdges, LLSequenceEdges, RawEdges),
    sort(RawEdges, Edges).

hl_intervals(OrderedSteps, Intervals) :-
    start_end_links_from_steps(OrderedSteps, Links, _UnmatchedStarts, _UnmatchedEnds),
    findall(
        interval(Action, step(StartID, start(Action)), EndStep, LLSteps),
        (
            member(start_end_link(StartID-start(Action), EndID-end(Action)), Links),
            is_hl_action(Action),
            EndStep = step(EndID, end(Action)),
            owned_ll_steps_after_start(StartID, OrderedSteps, LLSteps)
        ),
        Intervals
    ).

owned_ll_steps_after_start(StartID, OrderedSteps, LLSteps) :-
    findall(
        step(ID, Step),
        (
            member(step(ID, Step), OrderedSteps),
            ID > StartID
        ),
        FollowingSteps
    ),
    leading_ll_steps(FollowingSteps, LLSteps).

leading_ll_steps([], []).
leading_ll_steps([step(ID, Step)|Tail], [step(ID, Step)|LLTail]) :-
    ll_step(Step),
    !,
    leading_ll_steps(Tail, LLTail).
leading_ll_steps([_NonLLStep|_Tail], []).

assumption_edges_for_intervals([], []).
assumption_edges_for_intervals([interval(_Action, StartStep, EndStep, LLSteps)|Tail], Edges) :-
    StartStep = step(StartID, StartLabel),
    EndStep = step(EndID, EndLabel),
    findall(
        enabler(StartID-StartLabel, LLID-LLLabel, assumption(hl_start_enables_ll)),
        member(step(LLID, LLLabel), LLSteps),
        StartToLLEdges
    ),
    findall(
        enabler(LLID-LLLabel, EndID-EndLabel, assumption(ll_enables_hl_end)),
        member(step(LLID, LLLabel), LLSteps),
        LLToEndEdges
    ),
    append(
        [enabler(StartID-StartLabel, EndID-EndLabel, assumption(hl_start_enables_hl_end))|StartToLLEdges],
        LLToEndEdges,
        CurrentEdges
    ),
    assumption_edges_for_intervals(Tail, TailEdges),
    append(CurrentEdges, TailEdges, Edges).

ll_sequence_edges([], []).
ll_sequence_edges([interval(_Action, _StartStep, _EndStep, LLSteps)|Tail], Edges) :-
    ordered_ll_edges(LLSteps, CurrentEdges),
    ll_sequence_edges(Tail, TailEdges),
    append(CurrentEdges, TailEdges, Edges).

ordered_ll_edges(LLSteps, Edges) :-
    findall(
        enabler(ID1-Step1, ID2-Step2, assumption(ll_sequence)),
        (
            member(step(ID1, Step1), LLSteps),
            member(step(ID2, Step2), LLSteps),
            ID1 < ID2
        ),
        Edges
    ).

projected_hl_boundary_edges(OrderedSteps, CausalEdges, Edges) :-
    hl_intervals(OrderedSteps, Intervals),
    findall(
        enabler(SourceLLID-SourceLLStep, TargetLLID-TargetLLStep, assumption(hl_boundary_projection)),
        (
            member(enabler(SourceID-SourceStep, TargetID-TargetStep, _Reason), CausalEdges),
            project_boundary_step(source, step(SourceID, SourceStep), Intervals, step(SourceLLID, SourceLLStep)),
            project_boundary_step(target, step(TargetID, TargetStep), Intervals, step(TargetLLID, TargetLLStep)),
            (SourceLLID \= SourceID ; SourceLLStep \= SourceStep ; TargetLLID \= TargetID ; TargetLLStep \= TargetStep),
            SourceLLID < TargetLLID
        ),
        RawEdges
    ),
    sort(RawEdges, Edges).

project_boundary_step(_Role, step(ID, Step), _Intervals, step(ID, Step)) :-
    ll_step(Step),
    !.
project_boundary_step(source, step(ID, Step), Intervals, BoundaryStep) :-
    member(interval(_Action, step(ID, Step), _EndStep, LLSteps), Intervals),
    !,
    first_ll_step(LLSteps, BoundaryStep).
project_boundary_step(source, step(ID, Step), Intervals, BoundaryStep) :-
    member(interval(_Action, _StartStep, step(ID, Step), LLSteps), Intervals),
    !,
    last_ll_step(LLSteps, BoundaryStep).
project_boundary_step(target, step(ID, Step), Intervals, BoundaryStep) :-
    member(interval(_Action, step(ID, Step), _EndStep, LLSteps), Intervals),
    !,
    first_ll_step(LLSteps, BoundaryStep).
project_boundary_step(target, step(ID, Step), Intervals, BoundaryStep) :-
    member(interval(_Action, _StartStep, step(ID, Step), LLSteps), Intervals),
    !,
    last_ll_step(LLSteps, BoundaryStep).

first_ll_step([Step|_], Step).

last_ll_step([Step], Step) :- !.
last_ll_step([_|Tail], Step) :-
    last_ll_step(Tail, Step).

is_hl_action(Action) :-
    hl_d_action(Action, _PreStart, _PreEnd, _Overall, _EffStart, _EffEnd, _Duration).

ll_step(start(Action)) :-
    ll_d_action(Action, _PreStart, _PreEnd, _Overall, _EffStart, _EffEnd, _Duration).
ll_step(end(Action)) :-
    ll_d_action(Action, _PreStart, _PreEnd, _Overall, _EffStart, _EffEnd, _Duration).
