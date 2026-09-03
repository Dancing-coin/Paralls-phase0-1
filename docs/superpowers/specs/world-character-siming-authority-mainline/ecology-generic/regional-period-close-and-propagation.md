# Regional Period Close And Propagation

An explicit region+period close reads one immutable snapshot and applies the
fixed topology/cell/weather/resource/crop/species/hazard order. Propagation may
use only precompiled adjacency/watershed edges with bounded hops and sorted
frontiers. WorldMode cadence may request close but never writes implicitly.
