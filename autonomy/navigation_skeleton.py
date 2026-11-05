"""Navigation integration seams. Dry-run only; no robot connection or motor API.

Implement calibrated sensing and planning, validate in sim, then supply a local
executor separately. A camera image or an LLM direction is not a clearance test.
"""
from dataclasses import dataclass
from typing import Protocol
import math

@dataclass(frozen=True)
class Observation:
    received_at: float  # monotonic; receipt time is not sensor capture time
    frame_path: str
    pose_xyz_yaw: tuple[float, float, float, float]
    lidar_points: object  # replace with validated timestamped point-cloud type

@dataclass(frozen=True)
class Goal:
    x: float
    y: float
    frame: str = 'map'

@dataclass(frozen=True)
class World:
    updated_at: float
    frame: str
    localization_valid: bool
    clearance_verified: bool
    has_step_on_path: bool
    costmap: object

@dataclass(frozen=True)
class Velocity:
    forward: float = 0.0
    lateral: float = 0.0
    yaw_rate: float = 0.0

@dataclass(frozen=True)
class Decision:
    command: Velocity
    reason: str

class Mapper(Protocol):
    def update(self, obs: Observation) -> World:
        """Time-align camera/LiDAR/pose; transform to map; include unknown space,
        inflated obstacles, drop-offs and measured step geometry. Do not infer
        traversability from a single RGB image."""
        ...

class Planner(Protocol):
    def plan(self, world: World, goal: Goal) -> Velocity:
        """Return a bounded local command after collision checking the robot's
        swept footprint. Implement route planning + local obstacle handling."""
        ...

class DryRunNavigator:
    def __init__(self, mapper: Mapper, planner: Planner):
        self.mapper, self.planner = mapper, planner

    def tick(self, obs: Observation, goal: Goal, now: float) -> Decision:
        # Illustrative limits, not validated hardware safety limits.
        if not math.isfinite(now - obs.received_at) or not 0 <= now-obs.received_at <= 0.25:
            return Decision(Velocity(), 'stale/missing observation: hold')
        world = self.mapper.update(obs)
        if not 0 <= now-world.updated_at <= 0.25:
            return Decision(Velocity(), 'stale map: hold')
        if world.frame != goal.frame or not world.localization_valid:
            return Decision(Velocity(), 'localization/frame mismatch: hold')
        if not world.clearance_verified:
            return Decision(Velocity(), 'clearance unknown: hold')
        if world.has_step_on_path:
            return Decision(Velocity(), 'stair controller and geometry validation not implemented')
        command = self.planner.plan(world, goal)
        values = (command.forward, command.lateral, command.yaw_rate)
        if not all(math.isfinite(v) for v in values):
            return Decision(Velocity(), 'invalid planner command: hold')
        if abs(command.forward)>0.15 or abs(command.lateral)>0.10 or abs(command.yaw_rate)>0.25:
            return Decision(Velocity(), 'command exceeds illustrative limits: hold')
        return Decision(command, 'dry-run proposal only; no motion transmitted')

# Real execution integration still needs:
# - exact robot firmware/mode and stock obstacle-avoidance API validation
# - local watchdog independent of model/network stalls; stop on lost observations
# - one command owner, manual override, command expiry, tested stop semantics
# - stair-specific approach/alignment/climb/landing/abort controller and verified
#   step dimensions within this robot's capability, tested in simulation first
# - telemetry and recorded outcomes for every action
# No generic `execute(LLM_output)` or automatic stair enable switch belongs here.
