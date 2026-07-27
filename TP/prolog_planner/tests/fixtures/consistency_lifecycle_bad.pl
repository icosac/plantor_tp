pos(p1).
pos(p2).
agent(a1).
block(b1).
room(room_a).
robot(robot1).
ball(ball1).
gripper(gripper1).

init_state([
    at(b1, p1),
    clear(b1),
    available(a1),
    at_robot(robot1, room_a),
    at_ball(ball1, room_a),
    empty(gripper1)
]).

goal_state([
    at(b1, p2),
    clear(b1),
    available(a1),
    at_ball(ball1, room_a),
    empty(gripper1)
]).

hl_d_action(
    move_block(Agent, Block, From, To),
    [at(Block, From), clear(Block), available(Agent), agent(Agent), block(Block), pos(From), pos(To)],
    [clear(Block)],
    [],
    [del(at(Block, From)), del(clear(Block)), del(available(Agent))],
    [add(at(Block, To)), add(clear(Block)), add(available(Agent))],
    [1, 1]
).

hl_d_action(
    pick_up(Robot, Gripper, Ball, Room),
    [robot(Robot), gripper(Gripper), ball(Ball), room(Room), at_robot(Robot, Room), at_ball(Ball, Room), empty(Gripper), available(a1)],
    [],
    [at_robot(Robot, Room), at_ball(Ball, Room)],
    [del(empty(Gripper)), del(at_ball(Ball, Room))],
    [add(holding(Gripper, Ball)), add(empty(Gripper))],
    [1, 1]
).
