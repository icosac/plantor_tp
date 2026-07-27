pos(p1).
agent(a1).
block(b1).
block(b2).

init_state([
    ontable(b1),
    ontable(b2),
    at(b1, p1),
    at(b2, p1),
    clear(b1),
    clear(b2),
    available(a1)
]).

goal_state([
    ontable(b2),
    on(b1, b2),
    at(b1, p1),
    at(b2, p1),
    clear(b1),
    available(a1)
]).

hl_d_action(
    stack(Agent, Moved, Support, Pos),
    [available(Agent), ontable(Moved), at(Moved, Pos), at(Support, Pos), clear(Moved), clear(Support), agent(Agent), block(Moved), block(Support), pos(Pos), Moved \= Support],
    [clear(Support)],
    [clear(Support)],
    [del(available(Agent)), del(ontable(Moved)), del(clear(Moved))],
    [del(clear(Support)), add(on(Moved, Support)), add(clear(Moved)), add(available(Agent))],
    [1, 1]
).

hl_d_action(
    unstack(Agent, Moved, Support, Pos),
    [available(Agent), on(Moved, Support), at(Moved, Pos), at(Support, Pos), clear(Moved), agent(Agent), block(Moved), block(Support), pos(Pos), Moved \= Support],
    [],
    [],
    [del(available(Agent)), del(on(Moved, Support)), del(clear(Moved))],
    [add(ontable(Moved)), add(clear(Moved)), add(clear(Support)), add(available(Agent))],
    [1, 1]
).
