"""
engine/physics/contact_solver.py - PGS impulse solver with Baumgarte stabilization
and Coulomb friction for 2D contact resolution.

Resolves penetration and relative velocity between pairs of dynamic/kinematic/static
bodies using a projected Gauss-Seidel iterative scheme. Supports warm-starting via
a persistent impulse cache keyed by entity pair and clamps friction to Coulomb's cone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class ContactConstraint2D:
    """Per-contact constraint state for one contact point between two bodies.

    The normal points from entity A toward entity B.  The tangent is rotated 90°
    counter‑clockwise from the normal.
    """

    entity_a_id: int
    entity_b_id: int

    normal_x: float
    normal_y: float

    tangent_x: float  # -normal_y
    tangent_y: float  #  normal_x

    depth: float  # positive penetration depth

    mass_normal: float  # effective mass along normal
    mass_tangent: float  # effective mass along tangent

    restitution: float  # 0..1
    friction: float  # >= 0
    bias: float  # Baumgarte bias term

    accumulated_normal_impulse: float = 0.0
    accumulated_tangent_impulse: float = 0.0

    bounce_velocity: float = 0.0  # restitution * approach_velocity (pre-computed before PGS)

    contact_x: float = 0.0
    contact_y: float = 0.0

    rA_x: float = 0.0  # vector from body A center to contact point
    rA_y: float = 0.0
    rB_x: float = 0.0  # vector from body B center to contact point
    rB_y: float = 0.0

    is_bilateral: bool = False  # True para joints (permite impulso negativo), False para contactos

    contact_age: int = 0  # frames this contact has persisted (0 = new)


class ImpulseSolver2D:
    """Projected Gauss-Seidel impulse solver with warm-starting and friction."""

    BAUMGARTE_FACTOR: float = 0.2
    SLOP: float = 0.01
    MAX_BIAS: float = 10.0
    DEFAULT_ITERATIONS: int = 8
    CONTACT_RECYCLE_RADIUS: float = 0.5  # radio para matching de contactos entre frames

    def __init__(self) -> None:
        self._warm_start_cache: dict[
            tuple[int, int, int, int], tuple[float, float, int]
        ] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(
        self,
        constraints: list[ContactConstraint2D],
        bodies: dict[int, Any],
        dt: float,
        iterations: int = DEFAULT_ITERATIONS,
    ) -> None:
        """Resolve all contact constraints over *iterations* PGS passes."""

        # --- warm start (spatial contact matching) ------------------------
        for c in constraints:
            key = self._contact_key(
                c.entity_a_id, c.entity_b_id,
                c.contact_x, c.contact_y,
                self.CONTACT_RECYCLE_RADIUS,
            )
            cached = self._warm_start_cache.get(key)
            if cached is not None:
                c.accumulated_normal_impulse, c.accumulated_tangent_impulse, c.contact_age = cached

            body_a = bodies.get(c.entity_a_id)
            body_b = bodies.get(c.entity_b_id)
            if body_a is None or body_b is None:
                continue

            inv_a = self._effective_inv_mass(body_a)
            inv_b = self._effective_inv_mass(body_b)

            imp_x = c.normal_x * c.accumulated_normal_impulse + c.tangent_x * c.accumulated_tangent_impulse
            imp_y = c.normal_y * c.accumulated_normal_impulse + c.tangent_y * c.accumulated_tangent_impulse

            body_a.velocity_x -= imp_x * inv_a
            body_a.velocity_y -= imp_y * inv_a
            body_b.velocity_x += imp_x * inv_b
            body_b.velocity_y += imp_y * inv_b

            inv_inertia_a = self._effective_inv_inertia(body_a)
            inv_inertia_b = self._effective_inv_inertia(body_b)
            if inv_inertia_a > 0.0:
                body_a.angular_velocity -= (c.rA_x * imp_y - c.rA_y * imp_x) * inv_inertia_a
            if inv_inertia_b > 0.0:
                body_b.angular_velocity += (c.rB_x * imp_y - c.rB_y * imp_x) * inv_inertia_b

        # --- compute bounce velocities (before PGS, using initial velocities) ---
        for c in constraints:
            body_a = bodies.get(c.entity_a_id)
            body_b = bodies.get(c.entity_b_id)
            if body_a is None or body_b is None:
                continue
            rel_vx = getattr(body_b, "velocity_x", 0.0) - getattr(body_a, "velocity_x", 0.0)
            rel_vy = getattr(body_b, "velocity_y", 0.0) - getattr(body_a, "velocity_y", 0.0)
            vn_initial = rel_vx * c.normal_x + rel_vy * c.normal_y
            # Only bounce on approach (negative vn = bodies moving toward each other)
            c.bounce_velocity = c.restitution * min(0.0, vn_initial)

        # --- PGS iterations -----------------------------------------------
        for _ in range(iterations):
            for c in constraints:
                body_a = bodies.get(c.entity_a_id)
                body_b = bodies.get(c.entity_b_id)
                if body_a is None or body_b is None:
                    continue

                inv_mass_a = self._effective_inv_mass(body_a)
                inv_mass_b = self._effective_inv_mass(body_b)

                # Rotational inertia
                inv_inertia_a = self._effective_inv_inertia(body_a)
                inv_inertia_b = self._effective_inv_inertia(body_b)

                # Effective mass with rotation
                eff_mass_normal = self._effective_mass_with_rotation(
                    inv_mass_a, inv_mass_b,
                    c.rA_x, c.rA_y, c.rB_x, c.rB_y,
                    c.normal_x, c.normal_y,
                    inv_inertia_a, inv_inertia_b,
                )
                if eff_mass_normal <= 0.0:
                    continue

                rel_vx = body_b.velocity_x - body_a.velocity_x
                rel_vy = body_b.velocity_y - body_a.velocity_y

                vn = rel_vx * c.normal_x + rel_vy * c.normal_y
                vt = rel_vx * c.tangent_x + rel_vy * c.tangent_y

                # --- normal impulse ---------------------------------------
                if c.is_bilateral:
                    jn = (-(c.bounce_velocity + vn + c.bias)) * eff_mass_normal
                else:
                    jn = (c.bias - c.bounce_velocity - vn) * eff_mass_normal
                old_normal = c.accumulated_normal_impulse
                if c.is_bilateral:
                    c.accumulated_normal_impulse = old_normal + jn  # sin clamp
                else:
                    c.accumulated_normal_impulse = max(0.0, old_normal + jn)
                jn = c.accumulated_normal_impulse - old_normal

                # --- tangent impulse (Coulomb friction, skipped for joints) ---
                if not c.is_bilateral:
                    eff_mass_tangent = self._effective_mass_with_rotation(
                        inv_mass_a, inv_mass_b,
                        c.rA_x, c.rA_y, c.rB_x, c.rB_y,
                        c.tangent_x, c.tangent_y,
                        inv_inertia_a, inv_inertia_b,
                    )
                    jt = -vt * eff_mass_tangent
                    jn_raw = c.friction * c.accumulated_normal_impulse
                    max_friction = jn_raw if math.isfinite(jn_raw) else float('inf')
                    old_tangent = c.accumulated_tangent_impulse
                    c.accumulated_tangent_impulse = max(-max_friction, min(max_friction, old_tangent + jt))
                    jt = c.accumulated_tangent_impulse - old_tangent
                else:
                    jt = 0.0

                # --- apply impulses to velocities (linear) -----------------
                imp_x = c.normal_x * jn + c.tangent_x * jt
                imp_y = c.normal_y * jn + c.tangent_y * jt

                body_a.velocity_x -= imp_x * inv_mass_a
                body_a.velocity_y -= imp_y * inv_mass_a
                body_b.velocity_x += imp_x * inv_mass_b
                body_b.velocity_y += imp_y * inv_mass_b

                # --- apply angular impulses ---------------------------------
                if inv_inertia_a > 0.0:
                    # Cross product: r × impulse in 2D
                    angular_impulse_a = c.rA_x * imp_y - c.rA_y * imp_x
                    body_a.angular_velocity -= angular_impulse_a * inv_inertia_a
                if inv_inertia_b > 0.0:
                    angular_impulse_b = c.rB_x * imp_y - c.rB_y * imp_x
                    body_b.angular_velocity += angular_impulse_b * inv_inertia_b

        # --- update warm-start cache (spatial) ----------------------------
        active_keys: set[tuple] = set()
        for c in constraints:
            key = self._contact_key(
                c.entity_a_id, c.entity_b_id,
                c.contact_x, c.contact_y,
                self.CONTACT_RECYCLE_RADIUS,
            )
            active_keys.add(key)
            age = c.contact_age + 1
            self._warm_start_cache[key] = (
                c.accumulated_normal_impulse,
                c.accumulated_tangent_impulse,
                age,
            )

        # prune stale pairs
        stale = [k for k in self._warm_start_cache if k not in active_keys]
        for k in stale:
            del self._warm_start_cache[k]

    def solve_positions(
        self,
        constraints: list[ContactConstraint2D],
        transforms: dict[int, Any],
        bodies: dict[int, Any],
        delta_time: float = 0.016,
        iterations: int = 3,
    ) -> None:
        """Resolve positional overlap using PGS iterations on transforms directly.

        Applies mass-weighted positional corrections to entity transforms.
        For contacts: pushes bodies apart along normal to resolve penetration.
        For bilateral (joints): corrects relative position toward constraint target.
        Correction scaled by abs(bias) * delta_time so stiffness affects convergence speed.
        """
        POSITION_CORRECTION_FACTOR: float = 0.2
        POSITION_SLOP: float = 0.005  # Allowable penetration before correction

        for _ in range(iterations):
            for c in constraints:
                transform_a = transforms.get(c.entity_a_id)
                transform_b = transforms.get(c.entity_b_id)
                if transform_a is None or transform_b is None:
                    continue

                body_a = bodies.get(c.entity_a_id)
                body_b = bodies.get(c.entity_b_id)

                inv_mass_a = self._effective_inv_mass(body_a) if body_a is not None else 0.0
                inv_mass_b = self._effective_inv_mass(body_b) if body_b is not None else 0.0
                total_inv = inv_mass_a + inv_mass_b
                if total_inv <= 1e-10:
                    continue

                if c.is_bilateral:
                    # Joint: correct toward target. bias sign gives direction.
                    # Scale correction by stiffness via bias: bias = error * stiffness / dt.
                    direction = 1.0 if c.bias >= 0.0 else -1.0
                    correction = abs(c.bias) * delta_time * POSITION_CORRECTION_FACTOR
                    if correction > c.depth:
                        correction = c.depth
                    correction *= direction
                else:
                    # Contact: push apart if penetrating beyond slop
                    if c.depth <= POSITION_SLOP:
                        continue
                    correction = (c.depth - POSITION_SLOP) * POSITION_CORRECTION_FACTOR
                    # Reduce correction for old stable contacts to prevent jitter
                    age_factor = 1.0 / (1.0 + c.contact_age * 0.1)
                    correction *= age_factor

                # Mass-weighted distribution
                ratio_a = inv_mass_a / total_inv
                ratio_b = inv_mass_b / total_inv

                # normal points from A toward B
                if c.is_bilateral:
                    # Bilateral: correction > 0 means too far apart — bring together
                    # A moves +normal (toward B), B moves -normal (toward A)
                    transform_a.x += correction * c.normal_x * ratio_a
                    transform_a.y += correction * c.normal_y * ratio_a
                    transform_b.x -= correction * c.normal_x * ratio_b
                    transform_b.y -= correction * c.normal_y * ratio_b
                else:
                    # Contact: push A away from B (-normal), B away from A (+normal)
                    transform_a.x -= correction * c.normal_x * ratio_a
                    transform_a.y -= correction * c.normal_y * ratio_a
                    transform_b.x += correction * c.normal_x * ratio_b
                    transform_b.y += correction * c.normal_y * ratio_b

                # --- apply rotational position correction ---
                inv_inertia_a = self._effective_inv_inertia(body_a) if body_a is not None else 0.0
                inv_inertia_b = self._effective_inv_inertia(body_b) if body_b is not None else 0.0

                if inv_inertia_a > 0.0 or inv_inertia_b > 0.0:
                    # Effective mass with rotation for position correction
                    rnA = c.rA_x * c.normal_y - c.rA_y * c.normal_x
                    rnB = c.rB_x * c.normal_y - c.rB_y * c.normal_x
                    rot_inv = total_inv + rnA * rnA * inv_inertia_a + rnB * rnB * inv_inertia_b
                    if rot_inv > 1e-10:
                        rot_mass = 1.0 / rot_inv
                        if inv_inertia_a > 0.0:
                            delta_angle_a = -rnA * correction * rot_mass * inv_inertia_a
                            transform_a.rotation += delta_angle_a
                        if inv_inertia_b > 0.0:
                            delta_angle_b = rnB * correction * rot_mass * inv_inertia_b
                            transform_b.rotation += delta_angle_b

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def warm_start_cache_size(self) -> int:
        """Number of active contact pairs in the warm-start cache."""
        return len(self._warm_start_cache)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _contact_key(
        entity_a_id: int, entity_b_id: int,
        contact_x: float = 0.0, contact_y: float = 0.0,
        recycle_radius: float = 0.5,
    ) -> tuple[int, int, int, int]:
        """Create a quantized spatial key for contact matching.

        Two contacts match if they belong to the same entity pair AND
        their world-space contact points are within recycle_radius of each other.
        """
        a, b = (entity_a_id, entity_b_id) if entity_a_id < entity_b_id else (entity_b_id, entity_a_id)
        # Quantize contact position to recycle_radius grid
        qx = int(contact_x / max(recycle_radius, 0.01))
        qy = int(contact_y / max(recycle_radius, 0.01))
        return (a, b, qx, qy)

    @staticmethod
    def _effective_inv_inertia(body: Any) -> float:
        """Return 1/inertia for dynamic bodies, 0.0 otherwise."""
        body_type = getattr(body, "body_type", "static")
        if body_type != "dynamic":
            return 0.0
        if getattr(body, "lock_rotation", False):
            return 0.0
        inertia = getattr(body, "inertia", 1.0)
        if not math.isfinite(inertia) or inertia <= 0.0:
            return 0.0
        return 1.0 / inertia

    @staticmethod
    def _effective_mass_with_rotation(
        inv_mass_a: float, inv_mass_b: float,
        rA_x: float, rA_y: float, rB_x: float, rB_y: float,
        normal_x: float, normal_y: float,
        inv_inertia_a: float, inv_inertia_b: float,
    ) -> float:
        """Compute effective mass including rotational inertia terms (Box2D formula)."""
        # Cross product: r × n in 2D = r.x * n.y - r.y * n.x
        rnA = rA_x * normal_y - rA_y * normal_x
        rnB = rB_x * normal_y - rB_y * normal_x
        inv_mass = inv_mass_a + inv_mass_b + rnA * rnA * inv_inertia_a + rnB * rnB * inv_inertia_b
        if inv_mass <= 1e-10:
            return 0.0
        return 1.0 / inv_mass

    @staticmethod
    def _effective_inv_mass(body: Any) -> float:
        """Return 1/mass for dynamic bodies, 0.0 otherwise.

        Bodies are expected to expose ``body_type`` (str) and ``mass`` (float).
        NaN/Inf masses are treated as infinite mass (inv = 0.0).
        """
        body_type = getattr(body, "body_type", "static")
        if body_type != "dynamic":
            return 0.0

        mass = getattr(body, "mass", 0.0)
        if not math.isfinite(mass) or mass <= 0.0:
            return 0.0
        return 1.0 / mass
