The Prolog planner should provide an output in the following format in order for the partial 
order plan and the STN to be generate correctly:

```
[planner] Plan found in time{cpu:0.008946716,inferences:200457,wall:0.008972883224487305}
	start(crane_unstack_to_ground(crane1,c2,c1,location1))
	end(crane_unstack_to_ground(crane1,c2,c1,location1))
	start(crane_load_robot(crane1,r1,c2,location1))
	end(crane_load_robot(crane1,r1,c2,location1))
	start(robot_move(r1,c2,location1,location2))
	end(robot_move(r1,c2,location1,location2))
[...]
[planner] LL Plan:	35-end(crane_unload_robot(crane2,r1,c2,location2))
	34-end(ll_open_gripper(crane2))
	33-start(ll_open_gripper(crane2))
	32-end(ll_lower_container(crane2,c2))
	31-start(ll_lower_container(crane2,c2))
	30-end(ll_close_gripper(crane2))
	29-start(ll_close_gripper(crane2))
[...]
[planner] Enablers:	enabler(0-start(crane_unstack_to_ground(crane1,c2,c1,location1)),1-start(ll_go_to_container(crane1,c2)),assumption(hl_start_enables_ll))
	enabler(0-start(crane_unstack_to_ground(crane1,c2,c1,location1)),2-end(ll_go_to_container(crane1,c2)),assumption(hl_start_enables_ll))
	enabler(0-start(crane_unstack_to_ground(crane1,c2,c1,location1)),3-start(ll_close_gripper(crane1)),assumption(hl_start_enables_ll))
	enabler(0-start(crane_unstack_to_ground(crane1,c2,c1,location1)),4-end(ll_close_gripper(crane1)),assumption(hl_start_enables_ll))
	enabler(0-start(crane_unstack_to_ground(crane1,c2,c1,location1)),5-start(ll_lift_container(crane1,c2)),assumption(hl_start_enables_ll))
	enabler(0-start(crane_unstack_to_ground(crane1,c2,c1,location1)),6-end(ll_lift_container(crane1,c2)),assumption(hl_start_enables_ll))
	enabler(0-start(crane_unstack_to_ground(crane1,c2,c1,location1)),7-start(ll_lower_container(crane1,c2)),assumption(hl_start_enables_ll))
[...]
[planner] Start/end link terms:	start_end_link(0-start(crane_unstack_to_ground(crane1,c2,c1,location1)),11-end(crane_unstack_to_ground(crane1,c2,c1,location1)))
	start_end_link(1-start(ll_go_to_container(crane1,c2)),2-end(ll_go_to_container(crane1,c2)))
	start_end_link(3-start(ll_close_gripper(crane1)),4-end(ll_close_gripper(crane1)))
	start_end_link(5-start(ll_lift_container(crane1,c2)),6-end(ll_lift_container(crane1,c2)))
	start_end_link(7-start(ll_lower_container(crane1,c2)),8-end(ll_lower_container(crane1,c2)))
	start_end_link(9-start(ll_open_gripper(crane1)),10-end(ll_open_gripper(crane1)))
[...]
[planner] Start/end links:
	0-start(crane_unstack_to_ground(crane1,c2,c1,location1)) <-> 11-end(crane_unstack_to_ground(crane1,c2,c1,location1))
	1-start(ll_go_to_container(crane1,c2)) <-> 2-end(ll_go_to_container(crane1,c2))
	3-start(ll_close_gripper(crane1)) <-> 4-end(ll_close_gripper(crane1))
	5-start(ll_lift_container(crane1,c2)) <-> 6-end(ll_lift_container(crane1,c2))
	7-start(ll_lower_container(crane1,c2)) <-> 8-end(ll_lower_container(crane1,c2))
	9-start(ll_open_gripper(crane1)) <-> 10-end(ll_open_gripper(crane1))
[...]
[enablers] Plan actions with enablers:
	0-start(crane_unstack_to_ground(crane1,c2,c1,location1)) <= []
	1-start(ll_go_to_container(crane1,c2)) <= [0]
	2-end(ll_go_to_container(crane1,c2)) <= [0,1]
	3-start(ll_close_gripper(crane1)) <= [0,2]
	4-end(ll_close_gripper(crane1)) <= [0,3]
	5-start(ll_lift_container(crane1,c2)) <= [0,2,4]
[...]
[planner] Duration constraints:
	0-start(crane_unstack_to_ground(crane1,c2,c1,location1)) => [1, 200]
	1-start(ll_go_to_container(crane1,c2)) => [1, 2]
	2-end(ll_go_to_container(crane1,c2)) => [1, 2]
	3-start(ll_close_gripper(crane1)) => [1, 2]
	4-end(ll_close_gripper(crane1)) => [1, 2]
	5-start(ll_lift_container(crane1,c2)) => [1, 2]
[...]
```