package {{APPLICATION_ID}}

import android.app.Activity
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.util.Log
import android.view.MotionEvent
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.Window
import android.view.WindowManager
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestWindowFeature(Window.FEATURE_NO_TITLE)
        window.setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN)
        setContentView(MotorGameView(this))
    }
}

private class MotorGameView(context: Context) : SurfaceView(context), SurfaceHolder.Callback, Runnable {
    private var thread: Thread? = null
    private var running = false
    private val runtime = MotorRuntime(context)

    init {
        holder.addCallback(this)
        isFocusable = true
    }

    override fun surfaceCreated(holder: SurfaceHolder) {
        runtime.load()
        running = true
        thread = Thread(this, "MotorAndroidRuntime").also { it.start() }
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        running = false
        thread?.join(1000)
        thread = null
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) = Unit

    override fun run() {
        var last = System.nanoTime()
        while (running) {
            val now = System.nanoTime()
            val dt = ((now - last) / 1_000_000_000.0f).coerceIn(0.0f, 0.05f)
            last = now
            runtime.update(dt, width.toFloat(), height.toFloat())
            val canvas = holder.lockCanvas()
            if (canvas != null) {
                try {
                    runtime.render(canvas)
                } finally {
                    holder.unlockCanvasAndPost(canvas)
                }
            }
            val frameMs = ((System.nanoTime() - now) / 1_000_000).toLong()
            if (frameMs < 16L) Thread.sleep(16L - frameMs)
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        runtime.onTouch(event)
        return true
    }
}

private data class Entity(
    val name: String,
    val active: Boolean,
    val tag: String,
    val layer: String,
    val parent: String?,
    val components: JSONObject,
)

private class MotorRuntime(private val context: Context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val bitmaps = mutableMapOf<String, Bitmap?>()
    private val inputState = mutableMapOf("horizontal" to 0.0f, "vertical" to 0.0f, "action_1" to 0.0f, "action_2" to 0.0f)
    private val activePointers = mutableMapOf<Int, Pair<Float, Float>>()
    private var config = JSONObject()
    private var scene = JSONObject()
    private var entities = mutableListOf<Entity>()
    private var sceneFlow = JSONObject()
    private var entryScene = ""
    private var touchReleasedX = 0.0f
    private var touchReleasedY = 0.0f
    private var touchReleased = false
    private var uiPressed: String? = null
    private var viewportW = 1280.0f
    private var viewportH = 720.0f

    fun load() {
        config = readJson("runtime_config.json")
        entryScene = config.optString("entry_scene", "levels/main_menu_scene.json")
        loadScene(entryScene)
    }

    fun loadScene(path: String): Boolean {
        return try {
            scene = readJson(path)
            entities = mutableListOf<Entity>().also { list ->
                val arr = scene.optJSONArray("entities") ?: JSONArray()
                for (i in 0 until arr.length()) {
                    val obj = arr.optJSONObject(i) ?: continue
                    list.add(
                        Entity(
                            name = obj.optString("name"),
                            active = obj.optBoolean("active", true),
                            tag = obj.optString("tag"),
                            layer = obj.optString("layer"),
                            parent = obj.optString("parent", "").ifBlank { null },
                            components = obj.optJSONObject("components") ?: JSONObject(),
                        )
                    )
                }
            }
            val metadata = scene.optJSONObject("feature_metadata") ?: JSONObject()
            sceneFlow = metadata.optJSONObject("scene_flow") ?: JSONObject()
            uiPressed = null
            true
        } catch (exc: Exception) {
            Log.e(TAG, "Scene load failed: $path", exc)
            false
        }
    }

    fun onTouch(event: MotionEvent) {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN, MotionEvent.ACTION_MOVE -> {
                activePointers.clear()
                for (i in 0 until event.pointerCount) {
                    activePointers[event.getPointerId(i)] = event.getX(i) to event.getY(i)
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> {
                val idx = event.actionIndex
                touchReleasedX = event.getX(idx)
                touchReleasedY = event.getY(idx)
                touchReleased = true
                activePointers.remove(event.getPointerId(idx))
                if (event.actionMasked == MotionEvent.ACTION_UP) activePointers.clear()
            }
            MotionEvent.ACTION_CANCEL -> {
                activePointers.clear()
                touchReleased = false
                uiPressed = null
            }
        }
    }

    fun update(dt: Float, width: Float, height: Float) {
        viewportW = width
        viewportH = height
        updateMobileControls()
        updateButtons()
        updatePlayerControllers()
        updatePhysics(dt)
        updateAnimator(dt)
        touchReleased = false
    }

    fun render(canvas: Canvas) {
        canvas.drawColor(Color.rgb(10, 12, 16))
        val camera = resolveCamera()
        for (entity in entities) {
            if (!entity.active || entity.components.has("Canvas") || entity.components.has("RectTransform")) continue
            drawWorldEntity(canvas, entity, camera)
        }
        for (entity in entities) {
            if (!entity.active || !entity.components.has("RectTransform")) continue
            drawUiEntity(canvas, entity)
        }
        drawMobileControls(canvas)
    }

    private fun updateMobileControls() {
        inputState.keys.toList().forEach { inputState[it] = 0.0f }
        val controlsEntity = entities.firstOrNull { it.components.has("MobileControls2D") && it.active } ?: return
        val controls = controlsEntity.components.optJSONObject("MobileControls2D") ?: return
        if (!controls.optBoolean("enabled", true)) return
        for ((_, point) in activePointers) {
            val x = point.first
            val y = point.second
            val stickX = viewportW * controls.optDouble("left_stick_anchor_x", 0.16).toFloat()
            val stickY = viewportH * controls.optDouble("left_stick_anchor_y", 0.78).toFloat()
            val stickRadius = controls.optDouble("left_stick_radius", 86.0).toFloat()
            val dx = x - stickX
            val dy = y - stickY
            val distance = hypot(dx, dy)
            if (controls.optBoolean("left_stick_enabled", true) && distance in 1.0f..stickRadius) {
                val deadzone = controls.optDouble("deadzone", 0.18).toFloat()
                val normalized = min(1.0f, distance / stickRadius)
                if (normalized >= deadzone) {
                    val scale = (normalized - deadzone) / max(0.001f, 1.0f - deadzone)
                    inputState["horizontal"] = (dx / distance * scale).coerceIn(-1.0f, 1.0f)
                    inputState["vertical"] = (-dy / distance * scale).coerceIn(-1.0f, 1.0f)
                }
            }
            if (buttonHit(controls, "action_1", x, y)) inputState["action_1"] = 1.0f
            if (buttonHit(controls, "action_2", x, y)) inputState["action_2"] = 1.0f
        }
    }

    private fun buttonHit(controls: JSONObject, prefix: String, x: Float, y: Float): Boolean {
        if (!controls.optBoolean("${prefix}_enabled", true)) return false
        val cx = viewportW * controls.optDouble("${prefix}_anchor_x", if (prefix == "action_1") 0.84 else 0.72).toFloat()
        val cy = viewportH * controls.optDouble("${prefix}_anchor_y", if (prefix == "action_1") 0.78 else 0.84).toFloat()
        val radius = controls.optDouble("${prefix}_radius", if (prefix == "action_1") 54.0 else 46.0).toFloat()
        return hypot(x - cx, y - cy) <= radius
    }

    private fun updateButtons() {
        val down = activePointers.values.firstOrNull()
        for (entity in entities) {
            val button = entity.components.optJSONObject("UIButton") ?: continue
            val rect = uiRect(entity)
            if (down != null && rect.contains(down.first, down.second)) uiPressed = entity.name
            if (touchReleased && uiPressed == entity.name && rect.contains(touchReleasedX, touchReleasedY)) {
                handleClick(button.optJSONObject("on_click") ?: JSONObject())
            }
        }
        if (touchReleased) uiPressed = null
    }

    private fun handleClick(action: JSONObject) {
        when (action.optString("type")) {
            "load_scene_flow" -> {
                val target = action.optString("target")
                val path = sceneFlow.optString(target)
                if (path.isNotBlank()) loadScene(path)
            }
            "load_scene" -> {
                val path = action.optString("path", action.optString("scene"))
                if (path.isNotBlank()) loadScene(path)
            }
        }
    }

    private fun updatePlayerControllers() {
        for (entity in entities) {
            val rb = entity.components.optJSONObject("RigidBody") ?: continue
            val controller = entity.components.optJSONObject("PlayerController2D") ?: continue
            if (!controller.optBoolean("enabled", true)) continue
            val speed = controller.optDouble("move_speed", 200.0).toFloat()
            val jump = controller.optDouble("jump_velocity", -380.0).toFloat()
            rb.put("velocity_x", inputState["horizontal"]!! * speed)
            if (inputState["action_1"]!! > 0.5f && rb.optBoolean("is_grounded", false)) {
                rb.put("velocity_y", jump)
                rb.put("is_grounded", false)
            }
            val animator = entity.components.optJSONObject("Animator")
            if (animator != null) {
                val state = when {
                    !rb.optBoolean("is_grounded", false) -> "jump"
                    abs(inputState["horizontal"] ?: 0.0f) > 0.1f -> "run"
                    else -> "idle"
                }
                if ((animator.optJSONObject("animations") ?: JSONObject()).has(state)) animator.put("current_state", state)
            }
        }
    }

    private fun updatePhysics(dt: Float) {
        val solids = entities.filter { entity ->
            entity.components.has("Collider") && !entity.components.optJSONObject("Collider")!!.optBoolean("is_trigger", false) &&
                entity.components.optJSONObject("RigidBody")?.optString("body_type", "static") != "dynamic"
        }
        for (entity in entities) {
            val transform = entity.components.optJSONObject("Transform") ?: continue
            val rb = entity.components.optJSONObject("RigidBody") ?: continue
            if (!rb.optBoolean("simulated", true) || rb.optString("body_type", "dynamic") != "dynamic") continue
            val gravity = 600.0f * rb.optDouble("gravity_scale", 1.0).toFloat()
            rb.put("velocity_y", rb.optDouble("velocity_y", 0.0).toFloat() + gravity * dt)
            val startY = transform.optDouble("y", 0.0).toFloat()
            transform.put("x", transform.optDouble("x", 0.0).toFloat() + rb.optDouble("velocity_x", 0.0).toFloat() * dt)
            transform.put("y", startY + rb.optDouble("velocity_y", 0.0).toFloat() * dt)
            rb.put("is_grounded", false)
            for (solid in solids) {
                val a = worldRect(entity)
                val b = worldRect(solid)
                if (a != null && b != null && RectF.intersects(a, b)) {
                    if (startY <= b.top) {
                        val ownH = a.height()
                        transform.put("y", b.top - ownH / 2.0f)
                        rb.put("velocity_y", 0.0)
                        rb.put("is_grounded", true)
                    }
                }
            }
        }
    }

    private fun updateAnimator(dt: Float) {
        for (entity in entities) {
            val animator = entity.components.optJSONObject("Animator") ?: continue
            val animations = animator.optJSONObject("animations") ?: continue
            val state = animator.optString("current_state", animator.optString("default_state", "idle"))
            val anim = animations.optJSONObject(state) ?: continue
            val frames = anim.optJSONArray("frames") ?: continue
            if (frames.length() == 0) continue
            val fps = anim.optDouble("fps", 8.0).toFloat()
            val elapsed = animator.optDouble("_elapsed", 0.0).toFloat() + dt
            val frameTime = 1.0f / max(0.1f, fps)
            if (elapsed >= frameTime) {
                animator.put("current_frame", (animator.optInt("current_frame", 0) + 1) % frames.length())
                animator.put("_elapsed", 0.0)
            } else {
                animator.put("_elapsed", elapsed)
            }
        }
    }

    private fun drawWorldEntity(canvas: Canvas, entity: Entity, camera: CameraState) {
        val rect = worldRect(entity) ?: return
        val dst = RectF(
            (rect.left - camera.x) * camera.zoom + camera.offsetX,
            (rect.top - camera.y) * camera.zoom + camera.offsetY,
            (rect.right - camera.x) * camera.zoom + camera.offsetX,
            (rect.bottom - camera.y) * camera.zoom + camera.offsetY,
        )
        val animator = entity.components.optJSONObject("Animator")
        val sprite = entity.components.optJSONObject("Sprite")
        val bitmapPath = animator?.assetPath("sprite_sheet") ?: animator?.optString("sprite_sheet_path", "")
            ?: sprite?.assetPath("texture") ?: sprite?.optString("texture_path", "") ?: ""
        val bitmap = loadBitmap(bitmapPath)
        if (bitmap != null && animator != null) {
            val fw = animator.optInt("frame_width", bitmap.width)
            val fh = animator.optInt("frame_height", bitmap.height)
            val animations = animator.optJSONObject("animations") ?: JSONObject()
            val state = animator.optString("current_state", animator.optString("default_state", "idle"))
            val frames = animations.optJSONObject(state)?.optJSONArray("frames")
            val frameIndex = frames?.optInt(min(animator.optInt("current_frame", 0), frames.length() - 1), 0) ?: 0
            val cols = max(1, bitmap.width / max(1, fw))
            val sx = (frameIndex % cols) * fw
            val sy = (frameIndex / cols) * fh
            canvas.drawBitmap(bitmap, android.graphics.Rect(sx, sy, sx + fw, sy + fh), dst, paint)
        } else if (bitmap != null) {
            canvas.drawBitmap(bitmap, null, dst, paint)
        } else {
            paint.color = when (entity.tag.lowercase()) {
                "hero", "player" -> Color.rgb(80, 180, 255)
                "hazard" -> Color.rgb(220, 60, 80)
                "goal" -> Color.rgb(255, 210, 90)
                else -> Color.rgb(95, 105, 118)
            }
            canvas.drawRect(dst, paint)
        }
    }

    private fun drawUiEntity(canvas: Canvas, entity: Entity) {
        val rect = uiRect(entity)
        val button = entity.components.optJSONObject("UIButton")
        val text = entity.components.optJSONObject("UIText")
        if (button != null && button.optBoolean("enabled", true)) {
            paint.color = color(button.optJSONArray(if (uiPressed == entity.name) "pressed_color" else "normal_color"), Color.rgb(72, 72, 72))
            canvas.drawRoundRect(rect, 8.0f, 8.0f, paint)
            drawCenteredText(canvas, button.optString("label", "Button"), rect, 24.0f, Color.WHITE)
        }
        if (text != null && text.optBoolean("enabled", true)) {
            drawCenteredText(canvas, text.optString("text", ""), rect, text.optDouble("font_size", 24.0).toFloat(), color(text.optJSONArray("color"), Color.WHITE))
        }
    }

    private fun drawMobileControls(canvas: Canvas) {
        val controls = entities.firstOrNull { it.components.has("MobileControls2D") }?.components?.optJSONObject("MobileControls2D") ?: return
        paint.style = Paint.Style.FILL
        paint.color = Color.argb((255 * controls.optDouble("opacity", 0.65)).toInt(), 255, 255, 255)
        val sx = viewportW * controls.optDouble("left_stick_anchor_x", 0.16).toFloat()
        val sy = viewportH * controls.optDouble("left_stick_anchor_y", 0.78).toFloat()
        canvas.drawCircle(sx, sy, controls.optDouble("left_stick_radius", 86.0).toFloat(), paint)
        val a1x = viewportW * controls.optDouble("action_1_anchor_x", 0.84).toFloat()
        val a1y = viewportH * controls.optDouble("action_1_anchor_y", 0.78).toFloat()
        canvas.drawCircle(a1x, a1y, controls.optDouble("action_1_radius", 54.0).toFloat(), paint)
        val a2x = viewportW * controls.optDouble("action_2_anchor_x", 0.72).toFloat()
        val a2y = viewportH * controls.optDouble("action_2_anchor_y", 0.84).toFloat()
        canvas.drawCircle(a2x, a2y, controls.optDouble("action_2_radius", 46.0).toFloat(), paint)
    }

    private fun drawCenteredText(canvas: Canvas, value: String, rect: RectF, size: Float, color: Int) {
        textPaint.color = color
        textPaint.textSize = size
        textPaint.textAlign = Paint.Align.CENTER
        val y = rect.centerY() - (textPaint.descent() + textPaint.ascent()) / 2.0f
        canvas.drawText(value, rect.centerX(), y, textPaint)
    }

    private fun uiRect(entity: Entity): RectF {
        val rt = entity.components.optJSONObject("RectTransform") ?: JSONObject()
        val w = rt.optDouble("width", 100.0).toFloat().let { if (it <= 0.0f) viewportW else it }
        val h = rt.optDouble("height", 40.0).toFloat().let { if (it <= 0.0f) viewportH else it }
        val ax = rt.optDouble("anchor_min_x", 0.5).toFloat()
        val ay = rt.optDouble("anchor_min_y", 0.5).toFloat()
        val px = rt.optDouble("pivot_x", 0.5).toFloat()
        val py = rt.optDouble("pivot_y", 0.5).toFloat()
        val x = viewportW * ax + rt.optDouble("anchored_x", 0.0).toFloat()
        val y = viewportH * ay + rt.optDouble("anchored_y", 0.0).toFloat()
        return RectF(x - w * px, y - h * py, x + w * (1.0f - px), y + h * (1.0f - py))
    }

    private fun worldRect(entity: Entity): RectF? {
        val t = entity.components.optJSONObject("Transform") ?: return null
        val c = entity.components.optJSONObject("Collider")
        val sprite = entity.components.optJSONObject("Sprite")
        val animator = entity.components.optJSONObject("Animator")
        val w = (c?.optDouble("width") ?: sprite?.optDouble("width") ?: animator?.optDouble("frame_width") ?: 64.0).toFloat() * t.optDouble("scale_x", 1.0).toFloat()
        val h = (c?.optDouble("height") ?: sprite?.optDouble("height") ?: animator?.optDouble("frame_height") ?: 64.0).toFloat() * t.optDouble("scale_y", 1.0).toFloat()
        val x = t.optDouble("x", 0.0).toFloat() + (c?.optDouble("offset_x", 0.0)?.toFloat() ?: 0.0f)
        val y = t.optDouble("y", 0.0).toFloat() + (c?.optDouble("offset_y", 0.0)?.toFloat() ?: 0.0f)
        return RectF(x - w / 2.0f, y - h / 2.0f, x + w / 2.0f, y + h / 2.0f)
    }

    private fun resolveCamera(): CameraState {
        val cameraEntity = entities.firstOrNull { it.components.has("Camera2D") }
        val camera = cameraEntity?.components?.optJSONObject("Camera2D")
        val offsetX = camera?.optDouble("offset_x", viewportW / 2.0)?.toFloat() ?: viewportW / 2.0f
        val offsetY = camera?.optDouble("offset_y", viewportH / 2.0)?.toFloat() ?: viewportH / 2.0f
        var x = cameraEntity?.components?.optJSONObject("Transform")?.optDouble("x", offsetX.toDouble())?.toFloat() ?: offsetX
        var y = cameraEntity?.components?.optJSONObject("Transform")?.optDouble("y", offsetY.toDouble())?.toFloat() ?: offsetY
        val follow = camera?.optString("follow_entity", "") ?: ""
        if (follow.isNotBlank()) {
            val ft = entities.firstOrNull { it.name == follow }?.components?.optJSONObject("Transform")
            if (ft != null) {
                x = ft.optDouble("x", x.toDouble()).toFloat()
                y = ft.optDouble("y", y.toDouble()).toFloat()
            }
        }
        x = clampNullable(x, camera, "clamp_left", "clamp_right")
        y = clampNullable(y, camera, "clamp_top", "clamp_bottom")
        return CameraState(x, y, offsetX, offsetY, camera?.optDouble("zoom", 1.0)?.toFloat() ?: 1.0f)
    }

    private fun clampNullable(value: Float, obj: JSONObject?, lowKey: String, highKey: String): Float {
        var out = value
        if (obj != null && !obj.isNull(lowKey)) out = max(out, obj.optDouble(lowKey).toFloat())
        if (obj != null && !obj.isNull(highKey)) out = min(out, obj.optDouble(highKey).toFloat())
        return out
    }

    private fun loadBitmap(path: String): Bitmap? {
        if (path.isBlank()) return null
        return bitmaps.getOrPut(path) {
            try {
                context.assets.open(path).use { BitmapFactory.decodeStream(it) }
            } catch (_: Exception) {
                null
            }
        }
    }

    private fun readJson(path: String): JSONObject {
        return context.assets.open(path).bufferedReader().use { JSONObject(it.readText()) }
    }

    private fun JSONObject.assetPath(key: String): String {
        val obj = optJSONObject(key)
        if (obj != null) return obj.optString("path", "")
        return optString(key, "")
    }

    private fun color(value: JSONArray?, fallback: Int): Int {
        if (value == null || value.length() < 3) return fallback
        return Color.argb(value.optInt(3, 255), value.optInt(0), value.optInt(1), value.optInt(2))
    }

    private data class CameraState(val x: Float, val y: Float, val offsetX: Float, val offsetY: Float, val zoom: Float)

    companion object {
        private const val TAG = "MotorGame"
    }
}
