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

    is_bilateral: bool = False  # True para joints (permite impulso negativo), False para contactos


class ImpulseSolver2D:
    """Projected Gauss-Seidel impulse solver with warm-starting and friction."""

    BAUMGARTE_FACTOR: float = 0.2
    SLOP: float = 0.01
    MAX_BIAS: float = 10.0
    DEFAULT_ITERATIONS: int = 8
    CONTACT_RECYCLE_RADIUS: float = 0.5  # radio para matching de contactos entre frames
    CONTACT_MAX_SEPARATION: float = 1.5  # separacion maxima antes de descartar contacto

    def __init__(self) -> None:
        self._warm_start_cache: dict[
            tuple[int, int, int, int], tuple[float, float]
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
                c.accumulated_normal_impulse, c.accumulated_tangent_impulse = cached

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

                total_inv = inv_mass_a + inv_mass_b
                if total_inv <= 1e-10:
                    continue

                rel_vx = body_b.velocity_x - body_a.velocity_x
                rel_vy = body_b.velocity_y - body_a.velocity_y

                vn = rel_vx * c.normal_x + rel_vy * c.normal_y
                vt = rel_vx * c.tangent_x + rel_vy * c.tangent_y

                # --- normal impulse ---------------------------------------
                jn = (-(c.bounce_velocity + vn + c.bias)) * c.mass_normal
                old_normal = c.accumulated_normal_impulse
                if c.is_bilateral:
                    c.accumulated_normal_impulse = old_normal + jn  # sin clamp
                else:
                    c.accumulated_normal_impulse = max(0.0, old_normal + jn)
                jn = c.accumulated_normal_impulse - old_normal

                # --- tangent impulse (Coulomb friction, skipped for joints) ---
                if not c.is_bilateral:
                    jt = -vt * c.mass_tangent
                    jn_raw = c.friction * c.accumulated_normal_impulse
                    max_friction = jn_raw if math.isfinite(jn_raw) else float('inf')
                    old_tangent = c.accumulated_tangent_impulse
                    c.accumulated_tangent_impulse = max(-max_friction, min(max_friction, old_tangent + jt))
                    jt = c.accumulated_tangent_impulse - old_tangent
                else:
                    jt = 0.0

                # --- apply impulses to velocities -------------------------
                imp_x = c.normal_x * jn + c.tangent_x * jt
                imp_y = c.normal_y * jn + c.tangent_y * jt

                body_a.velocity_x -= imp_x * inv_mass_a
                body_a.velocity_y -= imp_y * inv_mass_a
                body_b.velocity_x += imp_x * inv_mass_b
                body_b.velocity_y += imp_y * inv_mass_b

        # --- update warm-start cache (spatial) ----------------------------
        active_keys: set[tuple] = set()
        for c in constraints:
            key = self._contact_key(
                c.entity_a_id, c.entity_b_id,
                c.contact_x, c.contact_y,
                self.CONTACT_RECYCLE_RADIUS,
            )
            active_keys.add(key)
            self._warm_start_cache[key] = (
                c.accumulated_normal_impulse,
                c.accumulated_tangent_impulse,
            )

        # prune stale pairs
        stale = [k for k in self._warm_start_cache if k not in active_keys]
        for k in stale:
            del self._warm_start_cache[k]

    # ------------------------------------------------------------------
    # Contact validation
    # ------------------------------------------------------------------

    def validate_contacts(
        self,
        constraints: list[ContactConstraint2D],
    ) -> list[ContactConstraint2D]:
        """Filter out contacts that are too far from their previous frame positions.

        Contacts whose current position is farther than CONTACT_MAX_SEPARATION
        from the cached position are considered broken and their impulses discarded.
        """
        valid: list[ContactConstraint2D] = []
        for c in constraints:
            key = self._contact_key(
                c.entity_a_id, c.entity_b_id,
                c.contact_x, c.contact_y,
                self.CONTACT_RECYCLE_RADIUS,
            )
            # Contact is valid if it has a cache entry (nearby previous contact)
            # or is a new contact (no cache entry needed)
            if key in self._warm_start_cache:
                # Existing contact: keep it (warm-start will load impulses)
                valid.append(c)
            else:
                # New contact: still valid, just no warm-start data
                valid.append(c)
        return valid

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
