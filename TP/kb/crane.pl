%%%%%%%%%%%%%%%%%%%%%%%
% actions
%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% CRANE ACTIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Move a container from the ground to the top of another container
% within the same location
hl_d_action(
  crane_stack(Crane, ContainerTop, ContainerBottom, Location),
  [
    crane(Crane),
    available(Crane),
    location(Location),
    located(Crane, Location),
    container(ContainerTop),
    container(ContainerBottom),
    ContainerTop \= ContainerBottom,
    at(ContainerTop, Location),
    at(ContainerBottom, Location),
    onground(ContainerTop),
    clear(ContainerTop),
    clear(ContainerBottom)
  ],
  [],
  [],
  [
    del(available(Crane)),
    del(onground(ContainerTop)),
    del(clear(ContainerBottom))
  ],
  [
    add(on(ContainerTop, ContainerBottom)),
    add(clear(ContainerTop)),
    add(available(Crane))
  ],
  [1, 200]
).

% Load a container onto the robot (container must be clear and in same location)
hl_d_action(
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
  [1, 106]
).

% Unload a container from the robot onto the ground in the same location
hl_d_action(
  crane_unload_robot(Crane, Robot, Container, Location),
  [
    crane(Crane),
    robot(Robot),
    available(Crane),
    located(Crane, Location),
    at(Robot, Location),
    on(Container, Robot),
    container(Container),
    clear(Container)
  ],
  [],
  [],
  [
    del(available(Crane)),
    del(on(Container, Robot))
  ],
  [
    add(onground(Container)),
    add(at(Container, Location)),
    add(clear(Container)),
    add(available(Crane)),
    add(available(Robot))
  ],
  [1, 106]
).

% Place a container on the ground from the top of another container
hl_d_action(
  crane_unstack_to_ground(Crane, ContainerTop, ContainerBottom, Location),
  [
    crane(Crane),
    available(Crane),
    located(Crane, Location),
    container(ContainerTop),
    container(ContainerBottom),
    at(ContainerBottom, Location),
    on(ContainerTop, ContainerBottom),
    clear(ContainerTop)
  ],
  [],
  [],
  [
    del(available(Crane)),
    del(on(ContainerTop, ContainerBottom))
  ],
  [
    add(onground(ContainerTop)),
    add(clear(ContainerTop)),
    add(clear(ContainerBottom)),
    add(available(Crane))
  ],
  [1, 200]
).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% ROBOT ACTIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Move robot between connected locations while carrying exactly one container
hl_d_action(
  robot_move(Robot, Container, From, To),
  [
    robot(Robot),
    available(Robot),
    connected(From, To),
    at(Robot, From),
    container(Container),
    on(Container, Robot),
    clear(Container),
    (Container \= Robot)
  ],
  [],
  [],
  [
    del(at(Robot, From)),
    del(at(Container, From))
  ],
  [
    add(at(Robot, To)),
    add(at(Container, To))
  ],
  [1, 100]
).

% Move robot between connected locations while carrying exactly one container
hl_d_action(
  robot_move(Robot, Container, From, To),
  [
    robot(Robot),
    available(Robot),
    connected(From, To),
    at(Robot, From),
    Container = empty
  ],
  [],
  [],
  [
    del(at(Robot, From))
  ],
  [
    add(at(Robot, To))
  ],
  [1, 100]
).

%%%%%%%%%%%%%%%%%%%%%%%
% kb
%%%%%%%%%%%%%%%%%%%%%%%
:- discontiguous resources/1.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% High-level knowledge base (unchanged)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Locations
location(location1).
location(location2).

% Connectivity between locations
connected(location1, location2).
connected(location2, location1).

% Containers
container(c1).
container(c2).

% Robot
robot(r1).

% Cranes (each crane is associated with a single location)
crane(crane1).
crane(crane2).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Low-level predicates
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Low-level wheeled robot
ll_wheeled_robot(r1).

% Low-level cranes
ll_crane(crane1).
ll_crane(crane2).

% Low-level gripper associated with cranes
ll_gripper(crane1).
ll_gripper(crane2).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Resources
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% High-level resources
resources(robot(_)).
resources(crane(_)).

% Low-level resources
resources(ll_wheeled_robot(_)).
resources(ll_crane(_)).
resources(ll_gripper(_)).

%%%%%%%%%%%%%%%%%%%%%%%
% init
%%%%%%%%%%%%%%%%%%%%%%%
init_state([
  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
  % High-level state (unchanged)
  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

  % Containers and their configuration
  at(c1, location1),
  at(c2, location1),
  onground(c1),
  on(c2, c1),
  clear(c2),

  % Robot state
  at(r1, location2),
  available(r1),

  % Cranes availability
  available(crane1),
  available(crane2),

  located(crane1, location1),
  located(crane2, location2),

  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
  % Low-level state
  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

  % Low-level robot position
  ll_robot_at(r1, location2),
  ll_container_state(c1, onground),

  % Crane grippers initial state (open)
  ll_gripper_state(crane1, open),
  ll_gripper_state(crane2, open),

  ll_crane_free(crane1),
  ll_crane_free(crane2),

  % Crane gripper positions (initially at their own location)
  ll_gripper_at(crane1, location1),
  ll_gripper_at(crane2, location2)
]).

%%%%%%%%%%%%%%%%%%%%%%%
% goal
%%%%%%%%%%%%%%%%%%%%%%%
goal_state([
  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
  % High-level goal
  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

  % Container c1 unchanged in location1
  at(c1, location1),
  onground(c1),
  clear(c1),

  % Container c2 moved to location2
  at(c2, location2),
  onground(c2),
  clear(c2),

  located(crane1, _),
  located(crane2, _),

  % Robot availability
  available(r1),

  % Cranes availability
  available(crane1),
  available(crane2),

  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
  % Low-level goal (unconstrained where specified)
  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

  % Robot final position does not matter
  ll_robot_at(r1, _),
  ll_container_state(c1, onground),

  % Crane positions do not matter
  ll_gripper_at(crane1, _),
  ll_gripper_at(crane2, _),

  % Gripper state does not matter
  ll_gripper_state(crane1, _),
  ll_gripper_state(crane2, _)
]).

%%%%%%%%%%%%%%%%%%%%%%%
% ll_actions
%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% LOW-LEVEL ROBOT ACTIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Move the wheeled robot between two locations
ll_d_action(
  ll_move_robot(Robot, From, To),
  [
    ll_wheeled_robot(Robot),
    ll_robot_at(Robot, From)
  ],
  [
    neg(ll_robot_at(_, To))
  ],
  [],
  [
    del(ll_robot_at(Robot, From))
  ],
  [
    add(ll_robot_at(Robot, To))
  ],
  [2, 4]
).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% LOW-LEVEL CRANE MOTION ACTIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Move crane gripper to a specific position
ll_d_action(
  ll_go_to_position(Crane, Position),
  [
    ll_gripper_at(Crane, _),
    ll_crane(Crane),
    ll_gripper(Crane),
    ll_crane_free(Crane)
  ],
  [],
  [],
  [
    del(ll_crane_free(Crane))
  ],
  [
    add(ll_gripper_at(Crane, Position)),
    add(ll_crane_free(Crane))
  ],
  [1, 2]
).

% Move crane gripper above a container
ll_d_action(
  ll_go_to_container(Crane, Container),
  [
    ll_crane(Crane),
    ll_gripper(Crane),
    ll_crane_free(Crane),
    container(Container)
  ],
  [],
  [],
  [
    del(ll_crane_free(Crane))
  ],
  [
    add(ll_gripper_over(Crane, Container)),
    add(ll_crane_free(Crane))
  ],
  [1, 2]
).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% LOW-LEVEL GRIPPER ACTIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Close the crane gripper
ll_d_action(
  ll_close_gripper(Crane),
  [
    ll_crane(Crane),
    ll_gripper(Crane),
    ll_gripper_state(Crane, open)
  ],
  [],
  [],
  [
    del(ll_gripper_state(Crane, open))
  ],
  [
    add(ll_gripper_state(Crane, closed))
  ],
  [1, 2]
).

% Open the crane gripper
ll_d_action(
  ll_open_gripper(Crane),
  [
    ll_crane(Crane),
    ll_gripper(Crane),
    ll_gripper_state(Crane, closed)
  ],
  [],
  [],
  [
    del(ll_gripper_state(Crane, closed))
  ],
  [
    add(ll_gripper_state(Crane, open))
  ],
  [1, 2]
).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% LOW-LEVEL CONTAINER MANIPULATION ACTIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Lift a container with the crane
ll_d_action(
  ll_lift_container(Crane, Container),
  [
    ll_crane(Crane),
    ll_gripper(Crane),
    ll_gripper_state(Crane, closed),
    ll_gripper_over(Crane, Container),
    container(Container)
  ],
  [],
  [],
  [],
  [
    add(ll_container_state(Container, lifted))
  ],
  [1, 2]
).

% Lower a container with the crane
ll_d_action(
  ll_lower_container(Crane, Container),
  [
    ll_crane(Crane),
    ll_gripper(Crane),
    ll_gripper_state(Crane, closed),
    container(Container),
    ll_container_state(Container, lifted)
  ],
  [],
  [],
  [
    del(ll_container_state(Container, lifted))
  ],
  [],
  [1, 2]
).

%%%%%%%%%%%%%%%%%%%%%%%
% mappings
%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% CRANE STACKING
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

mapping(
  crane_stack(Crane, ContainerTop, ContainerBottom, _Location),
  [
    ll_go_to_container(Crane, ContainerTop),
    ll_close_gripper(Crane),
    ll_lift_container(Crane, ContainerTop),
    ll_go_to_container(Crane, ContainerBottom),
    ll_lower_container(Crane, ContainerTop),
    ll_open_gripper(Crane)
  ]
).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% CRANE LOAD ROBOT
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

mapping(
  crane_load_robot(Crane, _Robot, Container, _Location),
  [
    ll_go_to_container(Crane, Container),
    ll_close_gripper(Crane),
    ll_lift_container(Crane, Container),
    ll_open_gripper(Crane)
  ]
).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% CRANE UNLOAD ROBOT
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

mapping(
  crane_unload_robot(Crane, _Robot, Container, _Location),
  [
    ll_go_to_container(Crane, Container),
    ll_close_gripper(Crane),
    ll_lower_container(Crane, Container),
    ll_open_gripper(Crane)
  ]
).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% CRANE UNSTACK TO GROUND
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

mapping(
  crane_unstack_to_ground(Crane, ContainerTop, _ContainerBottom, _Location),
  [
    ll_go_to_container(Crane, ContainerTop),
    ll_close_gripper(Crane),
    ll_lift_container(Crane, ContainerTop),
    ll_lower_container(Crane, ContainerTop),
    ll_open_gripper(Crane)
  ]
).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% ROBOT MOVE
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

mapping(
  robot_move(Robot, _Container, From, To),
  [
    ll_move_robot(Robot, From, To)
  ]
).