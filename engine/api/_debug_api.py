from __future__ import annotations

from typing import Dict, Optional, Union

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult


class DebugAPI(EngineAPIComponent):
    """Debug and profiler endpoints exposed by EngineAPI."""

    def reset_profiler(self, run_label: str = "default") -> ActionResult:
        """Reset the performance profiler for a new measurement run.

        Args:
            run_label: Label for the new profiling run (default "default").

        Returns:
            ActionResult confirming the profiler was reset.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        runtime.reset_profiler(run_label=run_label)
        return self.ok("Profiler reset", {"run_label": run_label})

    def get_profiler_report(self) -> Dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Get the current profiler report with timing data.

        Returns:
            Dictionary with profiler metrics including frames, total_time,
            frame_times, system timings, etc. Empty dict if engine not initialized.
        """
        runtime = self.runtime
        if runtime is None:
            return {}
        return runtime.get_profiler_report()

    def get_debug_profile(self) -> dict:
        """Get per-panel render timing breakdown from the editor layout.

        Returns:
            Dictionary with panel timing data. Empty dict if editor not available.
        """
        runtime = self.runtime
        if runtime is None:
            return {}
        layout = getattr(runtime, "editor_layout", None)
        if layout is not None and hasattr(layout, "get_debug_profile"):
            return layout.get_debug_profile()
        return {}

    def configure_debug_overlay(
        self,
        *,
        draw_colliders: Optional[bool] = None,
        draw_labels: Optional[bool] = None,
        draw_tile_chunks: Optional[bool] = None,
        draw_camera: Optional[bool] = None,
        primitives: Optional[list[Dict[str, Union[str, int, float, bool, list, dict, None]]]] = None,
    ) -> ActionResult:
        """Configure debug rendering overlay options for the viewport.

        Args:
            draw_colliders: If not None, toggle collider wireframe rendering.
            draw_labels: If not None, toggle entity name label rendering.
            draw_tile_chunks: If not None, toggle tile chunk boundary rendering.
            draw_camera: If not None, toggle camera frustum rendering.
            primitives: If not None, set custom debug primitive draw list.

        Returns:
            ActionResult with the current debug overlay state.
        """
        runtime = self.runtime
        if runtime is None or runtime.render_system is None:
            return self.fail("Render system not ready")
        runtime.debug_draw_colliders = runtime.debug_draw_colliders if draw_colliders is None else bool(draw_colliders)
        runtime.debug_draw_labels = runtime.debug_draw_labels if draw_labels is None else bool(draw_labels)
        runtime.render_system.set_debug_options(
            draw_colliders=draw_colliders,
            draw_labels=draw_labels,
            draw_tile_chunks=draw_tile_chunks,
            draw_camera=draw_camera,
        )
        if primitives is not None:
            runtime.render_system.set_debug_primitives(primitives)
        return self.ok("Debug overlay configured", runtime.render_system.get_debug_state())

    def clear_debug_primitives(self) -> ActionResult:
        """Remove all custom debug draw primitives from the overlay.

        Returns:
            ActionResult confirming primitives were cleared.
        """
        runtime = self.runtime
        if runtime is None or runtime.render_system is None:
            return self.fail("Render system not ready")
        runtime.render_system.clear_debug_primitives()
        return self.ok("Debug primitives cleared")

    def get_debug_geometry_dump(
        self,
        viewport_width: int = 800,
        viewport_height: int = 600,
    ) -> Dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Get a dump of all debug geometry currently being rendered.

        Args:
            viewport_width: Viewport width for coordinate calculations.
            viewport_height: Viewport height for coordinate calculations.

        Returns:
            Dictionary with lists of colliders, labels, tile chunks, camera
            info, and primitives being drawn.
        """
        runtime = self.runtime
        if runtime is None or runtime.render_system is None or runtime.world is None:
            return {}
        return runtime.render_system.get_debug_geometry_dump(
            runtime.world,
            viewport_size=(float(viewport_width), float(viewport_height)),
        )
