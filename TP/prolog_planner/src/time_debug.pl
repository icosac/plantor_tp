%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%                        TIME DEBUGGING HELPERS                              %%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

:- dynamic time_debug/1.
time_debug(false).

enable_time_debug  :- retractall(time_debug(_)), assertz(time_debug(true)).
disable_time_debug :- retractall(time_debug(_)), assertz(time_debug(false)).

time_emit(Format) :-
    time_debug(true)
    -> format(Format)
    ;  true.

time_emit(Format, Args) :-
    time_debug(true)
    -> format(Format, Args)
    ;  true.

time_call(Goal, Time) :-
    time_debug(true)
    -> call_time(Goal, Time)
    ;  (call(Goal), Time = none).
