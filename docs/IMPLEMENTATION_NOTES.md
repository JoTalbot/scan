# Implementation notes

This batch intentionally uses the existing `job_state.py` persistence model and `router_detect.py` evidence model rather than introducing a second state store or detector API.

The dispatcher remains a subprocess boundary. It does not infer authorization from discovery results. The child scanner is invoked with a constructed argv list and no shell target interpolation.

The state transition is:

`running -> running (partial shards) -> completed (all declared shards)`

A successful shard is represented by a stable `shard:<id>` marker. Repeated execution of the same shard observes the marker and exits without launching another scan.
