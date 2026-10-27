# AFSIM syntax fragments (the retriever's corpus)

## event_output

```text
event_output
   file output/scenario.evt
   enable WEAPON_FIRED
   enable WEAPON_HIT
   enable PLATFORM_BROKEN
   enable PLATFORM_ADDED
end_event_output
```

Point: with no enable list the .evt is zero bytes and nothing is reported. PLATFORM_KILLED is deprecated in 2.9; use PLATFORM_BROKEN.

## platform_type: the six components

```text
platform_type BLUE_FTR WSF_PLATFORM
   icon Fighter
   side blue
   mover WSF_AIR_MOVER
      update_interval 0.1 sec
   end_mover
   sensor radar WSF_RADAR_SENSOR
      ...parameters...
   end_sensor
   weapon swordfish WSF_IMPLICIT_WEAPON
      quantity 2
      weapon_effects BLAST_100
   end_weapon
   processor brain WSF_SCRIPT_PROCESSOR
      ...state machine...
   end_processor
end_platform_type
```

Point: type names are a closed namespace; a platform instance may reference only a type that is defined.

## position and route

```text
platform blue_ftr BLUE_FTR
   side blue
   position 40.0000n 116.0000e altitude 8000 m
   route
      position 40.0000n 116.0000e altitude 8000 m speed 500 kts
      position 40.2000n 116.1000e altitude 8000 m speed 500 kts
   end_route
end_platform
```

Point: position is latitude, longitude, then an optional altitude; speed appears only on route waypoints; duplicated waypoints report Coincident waypoints!.

## execute: timed scripts

```text
execute at_time 31.0 sec absolute
   PLATFORM.TurnToRelativeHeading(30.0, 10.0);
end_execute
```

Point: the time must be greater than 0 (0.0 reports Expected value '0' to be > 0); inside a platform block the PLATFORM variable is available.

## Globals and scripts

```text
script_variables
   double gAlt = 8000.0;
end_script_variables
```

Point: global script_variables must precede every include_once, or the run reports Unknown identifier.

## Random numbers and adjudication

```text
bool hit = MATH.RandomBernoulli(0.6);
```

Point: MATH.RandomBernoulli(p) draws from the simulation's main random source, so random_seed makes it reproducible.
