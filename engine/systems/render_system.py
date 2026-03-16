"""
engine/systems/render_system.py - Sistema de renderizado.
"""

from __future__ import annotations

from typing import Any, Optional

import pyray as rl

from engine.assets.asset_service import AssetService
from engine.components.animator import Animator
from engine.components.camera2d import Camera2D
from engine.components.collider import Collider
from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.resources.texture_manager import TextureManager


class RenderSystem:
    """Renderiza entidades y resuelve la camara logica del juego."""

    PLACEHOLDER_WIDTH: int = 32
    PLACEHOLDER_HEIGHT: int = 32
    PLACEHOLDER_COLOR = rl.SKYBLUE

    DEBUG_DRAW_COLLIDERS: bool = True

    def __init__(self) -> None:
        self._texture_manager: TextureManager = TextureManager()
        self._project_service: Any = None
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None

    def set_project_service(self, project_service: Any) -> None:
        self._project_service = project_service
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

    def reset_project_resources(self) -> None:
        self._texture_manager.unload_all()

    def render(
        self,
        world: World,
        override_camera: Optional[rl.Camera2D] = None,
        use_world_camera: bool = True,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> None:
        camera = override_camera
        if camera is None and use_world_camera:
            camera = self._build_camera_from_world(world, viewport_size=viewport_size)
        if camera is not None:
            rl.begin_mode_2d(camera)

        for entity in self._sorted_render_entities(world):
            transform = entity.get_component(Transform)
            if transform is None:
                continue
            self._render_entity(entity, transform)
            if self.DEBUG_DRAW_COLLIDERS:
                collider = entity.get_component(Collider)
                if collider is not None and collider.enabled:
                    self._draw_collider(transform, collider)

        if world.selected_entity_name:
            selected_entity = world.get_entity_by_name(world.selected_entity_name)
            if selected_entity is not None:
                self._draw_selection_highlight(selected_entity)

        if camera is not None:
            rl.end_mode_2d()

    def _sorted_render_entities(self, world: World) -> list[Entity]:
        entities = world.get_entities_with(Transform)
        sorting_layers = world.feature_metadata.get("render_2d", {}).get("sorting_layers", ["Default"])
        sorting_index = {name: index for index, name in enumerate(sorting_layers)}

        def sort_key(entity: Entity) -> tuple[int, int, int, int]:
            render_order = entity.get_component(RenderOrder2D)
            transform = entity.get_component(Transform)
            layer_name = render_order.sorting_layer if render_order is not None and render_order.enabled else "Default"
            order_in_layer = render_order.order_in_layer if render_order is not None and render_order.enabled else 0
            layer_index = sorting_index.get(layer_name, len(sorting_index))
            depth = transform.depth if transform is not None else 0
            return (layer_index, order_in_layer, depth, entity.id)

        return sorted(entities, key=sort_key)

    def _build_camera_from_world(
        self,
        world: World,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> Optional[rl.Camera2D]:
        primary_entity = None
        for entity in world.get_entities_with(Transform, Camera2D):
            camera_component = entity.get_component(Camera2D)
            if camera_component is not None and camera_component.enabled and camera_component.is_primary:
                primary_entity = entity
                break
        if primary_entity is None:
            return None

        transform = primary_entity.get_component(Transform)
        camera_component = primary_entity.get_component(Camera2D)
        if transform is None or camera_component is None:
            return None

        target_x = transform.x
        target_y = transform.y
        follow_target = world.get_entity_by_name(camera_component.follow_entity) if camera_component.follow_entity else None
        if follow_target is not None and follow_target.active:
            follow_transform = follow_target.get_component(Transform)
            if follow_transform is not None and follow_transform.enabled:
                target_x, target_y = self._resolve_camera_target(camera_component, follow_transform, viewport_size)

        target_x, target_y = self._apply_camera_clamp(camera_component, target_x, target_y)

        camera = rl.Camera2D()
        camera.target = rl.Vector2(target_x, target_y)
        camera.offset = rl.Vector2(camera_component.offset_x, camera_component.offset_y)
        camera.rotation = camera_component.rotation
        camera.zoom = camera_component.zoom
        return camera

    def _resolve_camera_target(
        self,
        camera_component: Camera2D,
        follow_transform: Transform,
        viewport_size: Optional[tuple[float, float]],
    ) -> tuple[float, float]:
        target_x = follow_transform.x
        target_y = follow_transform.y
        if camera_component.framing_mode != "platformer":
            camera_component._runtime_target_x = target_x
            camera_component._runtime_target_y = target_y
            camera_component._has_recentred = True
            return target_x, target_y

        view_width = viewport_size[0] if viewport_size else 800.0
        view_height = viewport_size[1] if viewport_size else 600.0
        dead_zone_width = camera_component.dead_zone_width or (view_width * 0.18)
        dead_zone_height = camera_component.dead_zone_height or (view_height * 0.12)
        vertical_bias = max(0.0, view_height * 0.12)
        desired_y = target_y - vertical_bias

        if camera_component.recenter_on_play and not camera_component._has_recentred:
            camera_component._runtime_target_x = target_x
            camera_component._runtime_target_y = desired_y
            camera_component._has_recentred = True
            return target_x, desired_y

        current_x = camera_component._runtime_target_x
        current_y = camera_component._runtime_target_y
        if not camera_component._has_recentred:
            current_x = target_x
            current_y = desired_y
            camera_component._has_recentred = True

        half_dead_zone_x = dead_zone_width * 0.5
        half_dead_zone_y = dead_zone_height * 0.5
        if target_x > current_x + half_dead_zone_x:
            current_x = target_x - half_dead_zone_x
        elif target_x < current_x - half_dead_zone_x:
            current_x = target_x + half_dead_zone_x

        if desired_y > current_y + half_dead_zone_y:
            current_y = desired_y - half_dead_zone_y
        elif desired_y < current_y - half_dead_zone_y:
            current_y = desired_y + half_dead_zone_y

        camera_component._runtime_target_x = current_x
        camera_component._runtime_target_y = current_y
        return current_x, current_y

    def _apply_camera_clamp(
        self,
        camera_component: Camera2D,
        target_x: float,
        target_y: float,
    ) -> tuple[float, float]:
        if camera_component.clamp_left is not None:
            target_x = max(camera_component.clamp_left, target_x)
        if camera_component.clamp_right is not None:
            target_x = min(camera_component.clamp_right, target_x)
        if camera_component.clamp_top is not None:
            target_y = max(camera_component.clamp_top, target_y)
        if camera_component.clamp_bottom is not None:
            target_y = min(camera_component.clamp_bottom, target_y)
        return target_x, target_y

    def _draw_selection_highlight(self, entity: Entity) -> None:
        transform = entity.get_component(Transform)
        if transform is None:
            return

        width = self.PLACEHOLDER_WIDTH
        height = self.PLACEHOLDER_HEIGHT
        offset_x = 0.5
        offset_y = 0.5

        sprite = entity.get_component(Sprite)
        if sprite is not None and sprite.enabled:
            if sprite.width > 0:
                width = sprite.width
            elif sprite.texture_path:
                texture = self._load_texture(sprite.get_texture_reference(), sprite.texture_path, sync_callback=sprite.sync_texture_reference)
                if texture.id != 0:
                    width = texture.width
                    height = texture.height
            if sprite.height > 0:
                height = sprite.height
            offset_x = sprite.origin_x
            offset_y = sprite.origin_y

        animator = entity.get_component(Animator)
        if animator is not None and animator.enabled:
            current_slice = animator.get_current_slice_name()
            slice_rect = self._asset_service.get_slice_rect(animator.get_sprite_sheet_reference(), current_slice) if (self._asset_service is not None and current_slice) else None
            if slice_rect is not None:
                width = int(slice_rect["width"])
                height = int(slice_rect["height"])
            else:
                if animator.frame_width > 0:
                    width = animator.frame_width
                if animator.frame_height > 0:
                    height = animator.frame_height

        width *= transform.scale_x
        height *= transform.scale_y
        left = transform.x - (width * offset_x)
        top = transform.y - (height * offset_y)

        import time

        pulse = (time.time() * 10) % 255
        alpha = int(150 + (pulse / 255) * 100)
        color = rl.Color(255, 255, 0, alpha)
        rl.draw_rectangle_lines_ex(rl.Rectangle(left, top, width, height), 2, color)
        rl.draw_text(entity.name, int(left), int(top - 20), 10, rl.YELLOW)

    def _render_entity(self, entity: Entity, transform: Transform) -> None:
        animator = entity.get_component(Animator)
        sprite = entity.get_component(Sprite)
        if animator is not None and animator.enabled and animator.sprite_sheet:
            self._draw_animated_sprite(transform, animator)
        elif sprite is not None and sprite.enabled and sprite.texture_path:
            self._draw_sprite(transform, sprite)
        else:
            self._draw_placeholder(entity.name, transform)

    def _draw_animated_sprite(self, transform: Transform, animator: Animator) -> None:
        texture = self._load_texture(animator.get_sprite_sheet_reference(), animator.sprite_sheet, sync_callback=animator.sync_sprite_sheet_reference)
        if texture.id == 0:
            return

        slice_name = animator.get_current_slice_name()
        slice_rect = self._asset_service.get_slice_rect(animator.get_sprite_sheet_reference(), slice_name) if (self._asset_service is not None and slice_name) else None
        if slice_rect is not None:
            src_x = int(slice_rect["x"])
            src_y = int(slice_rect["y"])
            src_w = int(slice_rect["width"])
            src_h = int(slice_rect["height"])
        else:
            sheet_columns = texture.width // max(1, animator.frame_width)
            if sheet_columns <= 0:
                sheet_columns = 1
            src_x, src_y, src_w, src_h = animator.get_source_rect(sheet_columns)

        dest_w = int(src_w * transform.scale_x)
        dest_h = int(src_h * transform.scale_y)
        dest_x = transform.x - dest_w / 2
        dest_y = transform.y - dest_h / 2
        if animator.flip_x:
            source_rect = rl.Rectangle(src_x + src_w, src_y, -src_w, src_h)
        else:
            source_rect = rl.Rectangle(src_x, src_y, src_w, src_h)
        dest_rect = rl.Rectangle(dest_x, dest_y, dest_w, dest_h)
        rl.draw_texture_pro(texture, source_rect, dest_rect, rl.Vector2(0, 0), transform.rotation, rl.WHITE)
        state_text = f"{animator.current_state}[{animator.current_frame}]"
        rl.draw_text(state_text, int(dest_x), int(dest_y - 15), 10, rl.YELLOW)

    def _draw_sprite(self, transform: Transform, sprite: Sprite) -> None:
        texture = self._load_texture(sprite.get_texture_reference(), sprite.texture_path, sync_callback=sprite.sync_texture_reference)
        if texture.id == 0:
            return

        width = sprite.width if sprite.width > 0 else texture.width
        height = sprite.height if sprite.height > 0 else texture.height
        width = int(width * transform.scale_x)
        height = int(height * transform.scale_y)
        dest_x = transform.x - (width * sprite.origin_x)
        dest_y = transform.y - (height * sprite.origin_y)

        source_width = texture.width if not sprite.flip_x else -texture.width
        source_height = texture.height if not sprite.flip_y else -texture.height
        source_rect = rl.Rectangle(0, 0, source_width, source_height)
        dest_rect = rl.Rectangle(dest_x, dest_y, width, height)
        tint = rl.Color(*sprite.tint)
        rl.draw_texture_pro(texture, source_rect, dest_rect, rl.Vector2(0, 0), transform.rotation, tint)

    def _draw_placeholder(self, name: str, transform: Transform) -> None:
        width = int(self.PLACEHOLDER_WIDTH * transform.scale_x)
        height = int(self.PLACEHOLDER_HEIGHT * transform.scale_y)
        rect_x = int(transform.x - width / 2)
        rect_y = int(transform.y - height / 2)
        rl.draw_rectangle(rect_x, rect_y, width, height, self.PLACEHOLDER_COLOR)
        rl.draw_text(name, rect_x, rect_y - 15, 10, rl.WHITE)

    def _draw_collider(self, transform: Transform, collider: Collider) -> None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        rl.draw_rectangle_lines(int(left), int(top), int(right - left), int(bottom - top), rl.GREEN)

    def _load_texture(self, reference: Any, fallback_path: str, sync_callback: Any = None) -> rl.Texture:
        entry = self._asset_resolver.resolve_entry(reference) if self._asset_resolver is not None else None
        if entry is not None:
            if sync_callback is not None:
                sync_callback(entry.get("reference", {}))
            return self._texture_manager.load(entry["absolute_path"], cache_key=entry.get("guid") or entry.get("path"))

        resolved_path = self._resolve_texture_path(fallback_path)
        return self._texture_manager.load(resolved_path, cache_key=resolved_path)

    def _resolve_texture_path(self, path: str) -> str:
        if self._project_service is None or not path:
            return path
        return self._project_service.resolve_path(path).as_posix()

    def cleanup(self) -> None:
        self._texture_manager.unload_all()
