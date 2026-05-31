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
import java.io.File
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
    private val controlCaptures = mutableMapOf<Int, String>()
    private var config = JSONObject()
    private var scene = JSONObject()
    private var entities = mutableListOf<Entity>()
    private var sceneFlow = JSONObject()
    private var entryScene = ""
    private var androidPythonRuntime = false
    private var sharedRuntimeBridge: SharedRuntimeBridge? = null
    private var scriptBridge: ScriptBehaviourBridge? = null
    private var activeRespawnName: String? = null
    private var touchPressedX = 0.0f
    private var touchPressedY = 0.0f
    private var touchPressed = false
    private var touchReleasedX = 0.0f
    private var touchReleasedY = 0.0f
    private var touchReleased = false
    private var uiPressed: String? = null
    private var runtimeError: String? = null
    private var viewportW = 1280.0f
    private var viewportH = 720.0f
    private var surfaceW = 1280.0f
    private var surfaceH = 720.0f

    fun load() {
        config = readJson("runtime_config.json")
        val window = config.optJSONObject("window") ?: JSONObject()
        viewportW = positiveFloat(window.optDouble("width", 1280.0), 1280.0f)
        viewportH = positiveFloat(window.optDouble("height", 720.0), 720.0f)
        androidPythonRuntime = config.optBoolean("android_python_runtime", false)
        if (androidPythonRuntime) {
            try {
                val runtimeDir = preparePythonRuntimeFiles()
                sharedRuntimeBridge = SharedRuntimeBridge(context)
                val snapshot = sharedRuntimeBridge?.create(runtimeDir.absolutePath, config)
                if (snapshot == null || !applyRuntimeSnapshot(snapshot)) {
                    setRuntimeError("Shared runtime did not return a valid scene snapshot.", snapshot)
                }
            } catch (exc: Exception) {
                setRuntimeError("Shared runtime preparation failed: ${exc.message ?: "unknown"}", null, exc)
            }
        } else {
            scriptBridge = ScriptBehaviourBridge(context)
        }
        entryScene = config.optString("entry_scene", "levels/main_menu_scene.json")
        if (!androidPythonRuntime) loadScene(entryScene)
    }

    fun loadScene(path: String): Boolean {
        if (androidPythonRuntime) {
            val snapshot = sharedRuntimeBridge?.loadScene(path) ?: return false
            return applyRuntimeSnapshot(snapshot)
        }
        return try {
            if (scene.length() > 0) {
                runScripts("on_stop", 0.0f)
            }
            scene = readJson(path)
            rebuildEntitiesFromScene()
            val metadata = scene.optJSONObject("feature_metadata") ?: JSONObject()
            sceneFlow = metadata.optJSONObject("scene_flow") ?: JSONObject()
            uiPressed = null
            controlCaptures.clear()
            activeRespawnName = null
            runScripts("on_play", 0.0f)
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
                    val mapped = screenToViewport(event.getX(i), event.getY(i))
                    if (mapped != null) activePointers[event.getPointerId(i)] = mapped
                }
                if (event.actionMasked == MotionEvent.ACTION_DOWN || event.actionMasked == MotionEvent.ACTION_POINTER_DOWN) {
                    val mapped = screenToViewport(event.getX(event.actionIndex), event.getY(event.actionIndex))
                    if (mapped != null) {
                        touchPressedX = mapped.first
                        touchPressedY = mapped.second
                        touchPressed = true
                    }
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> {
                val idx = event.actionIndex
                val mapped = screenToViewport(event.getX(idx), event.getY(idx))
                if (mapped != null) {
                    touchReleasedX = mapped.first
                    touchReleasedY = mapped.second
                    touchReleased = true
                } else {
                    touchReleased = false
                }
                val pointerId = event.getPointerId(idx)
                activePointers.remove(pointerId)
                controlCaptures.remove(pointerId)
                if (event.actionMasked == MotionEvent.ACTION_UP) activePointers.clear()
            }
            MotionEvent.ACTION_CANCEL -> {
                activePointers.clear()
                controlCaptures.clear()
                touchPressed = false
                touchReleased = false
                uiPressed = null
            }
        }
    }

    fun update(dt: Float, width: Float, height: Float) {
        surfaceW = max(1.0f, width)
        surfaceH = max(1.0f, height)
        if (androidPythonRuntime) {
            if (runtimeError != null) return
            val snapshot = sharedRuntimeBridge?.runFrame(dt, pointerStateJson())
            if (snapshot == null || !applyRuntimeSnapshot(snapshot)) {
                setRuntimeError("Shared runtime frame failed.", snapshot)
            }
            touchPressed = false
            touchReleased = false
            return
        }
        updateMobileControls()
        updateButtons()
        runScripts("on_update", dt)
        updatePlayerControllers()
        updateMovingPlatforms(dt)
        updatePhysics(dt)
        updateGameplaySemantics()
        updateAnimator(dt)
        touchReleased = false
    }

    fun render(canvas: Canvas) {
        updateSurfaceSize(canvas.width.toFloat(), canvas.height.toFloat())
        val frame = viewportFrame()
        canvas.drawColor(Color.BLACK)
        val error = runtimeError
        if (error != null) {
            drawRuntimeError(canvas, error)
            return
        }
        val saveCount = canvas.save()
        canvas.translate(frame.left, frame.top)
        canvas.scale(frame.width() / viewportW, frame.height() / viewportH)
        canvas.clipRect(0.0f, 0.0f, viewportW, viewportH)
        try {
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
        } finally {
            canvas.restoreToCount(saveCount)
        }
    }

    private fun positiveFloat(value: Double, fallback: Float): Float {
        val out = value.toFloat()
        return if (out > 0.0f) out else fallback
    }

    private fun preparePythonRuntimeFiles(): File {
        val runtimeDir = File(context.filesDir, "motor_runtime")
        val cacheKey = config.optString("android_runtime_cache_key", "uncached")
        val marker = File(runtimeDir, ".motor_runtime_cache_key")
        if (runtimeDir.exists() && marker.exists() && marker.readText() == cacheKey && File(runtimeDir, "runtime_config.json").exists()) {
            return runtimeDir
        }
        if (runtimeDir.exists()) runtimeDir.deleteRecursively()
        runtimeDir.mkdirs()
        for (assetPath in ANDROID_RUNTIME_ASSET_PATHS) {
            copyRuntimeAsset(assetPath, runtimeDir, required = assetPath in ANDROID_RUNTIME_REQUIRED_ASSET_PATHS)
        }
        marker.writeText(cacheKey)
        return runtimeDir
    }

    private fun copyRuntimeAsset(assetPath: String, root: File, required: Boolean) {
        try {
            copyAssetTree(assetPath, root)
        } catch (exc: Exception) {
            if (required) throw exc
            Log.i(TAG, "Optional Android runtime asset missing: $assetPath")
        }
    }

    private fun copyAssetTree(assetPath: String, root: File) {
        if (assetPath == "chaquopy" || assetPath.startsWith("chaquopy/")) return
        val children = context.assets.list(assetPath) ?: emptyArray()
        if (children.isNotEmpty()) {
            if (assetPath.isNotBlank()) File(root, assetPath).mkdirs()
            for (child in children) {
                val childPath = if (assetPath.isBlank()) child else "$assetPath/$child"
                copyAssetTree(childPath, root)
            }
            return
        }
        if (assetPath.isBlank()) return
        val target = File(root, assetPath)
        target.parentFile?.mkdirs()
        context.assets.open(assetPath).use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        }
    }

    private fun applyRuntimeSnapshot(snapshot: JSONObject): Boolean {
        if (!snapshot.optBoolean("ok", false)) {
            setRuntimeError("Shared runtime failed: ${snapshot.optString("error", "unknown")}", snapshot)
            return false
        }
        val scenePayload = snapshot.optJSONObject("scene")
        if (scenePayload == null) {
            setRuntimeError("Shared runtime returned no scene payload.", snapshot)
            return false
        }
        runtimeError = null
        scene = scenePayload
        rebuildEntitiesFromScene()
        val metadata = scene.optJSONObject("feature_metadata") ?: JSONObject()
        sceneFlow = metadata.optJSONObject("scene_flow") ?: JSONObject()
        uiPressed = null
        activeRespawnName = null
        return true
    }

    private fun setRuntimeError(message: String, snapshot: JSONObject? = null, exc: Exception? = null) {
        val traceback = snapshot?.optString("traceback", "") ?: ""
        val error = snapshot?.optString("error", "") ?: ""
        runtimeError = listOf(message, error, traceback).filter { it.isNotBlank() }.joinToString("\n").take(1800)
        if (exc != null) {
            Log.e(TAG, runtimeError ?: message, exc)
        } else {
            Log.e(TAG, runtimeError ?: message)
        }
    }

    private fun drawRuntimeError(canvas: Canvas, message: String) {
        canvas.drawColor(Color.rgb(18, 20, 24))
        val margin = 32.0f
        textPaint.color = Color.rgb(255, 220, 120)
        textPaint.textSize = 24.0f
        textPaint.textAlign = Paint.Align.LEFT
        canvas.drawText("Motor Android runtime error", margin, margin + 24.0f, textPaint)
        textPaint.color = Color.WHITE
        textPaint.textSize = 15.0f
        var y = margin + 60.0f
        for (line in wrapText(message, 58).take(14)) {
            canvas.drawText(line, margin, y, textPaint)
            y += 22.0f
        }
    }

    private fun wrapText(value: String, width: Int): List<String> {
        val out = mutableListOf<String>()
        for (raw in value.split('\n')) {
            var line = raw.trim()
            while (line.length > width) {
                out.add(line.substring(0, width))
                line = line.substring(width)
            }
            if (line.isNotBlank()) out.add(line)
        }
        return out.ifEmpty { listOf("Unknown runtime error. Check Logcat tag $TAG.") }
    }

    private fun pointerStateJson(): JSONObject {
        val pointer = activePointers.values.firstOrNull()
        if (pointer != null) {
            return JSONObject()
                .put("x", pointer.first)
                .put("y", pointer.second)
                .put("down", true)
                .put("pressed", touchPressed)
                .put("released", false)
        }
        if (touchReleased) {
            return JSONObject()
                .put("x", touchReleasedX)
                .put("y", touchReleasedY)
                .put("down", false)
                .put("pressed", false)
                .put("released", true)
        }
        if (touchPressed) {
            return JSONObject()
                .put("x", touchPressedX)
                .put("y", touchPressedY)
                .put("down", true)
                .put("pressed", true)
                .put("released", false)
        }
        return JSONObject()
    }

    private fun updateSurfaceSize(width: Float, height: Float) {
        surfaceW = max(1.0f, width)
        surfaceH = max(1.0f, height)
    }

    private fun viewportFrame(): RectF {
        val scale = min(surfaceW / viewportW, surfaceH / viewportH)
        val width = viewportW * scale
        val height = viewportH * scale
        val left = (surfaceW - width) / 2.0f
        val top = (surfaceH - height) / 2.0f
        return RectF(left, top, left + width, top + height)
    }

    private fun screenToViewport(screenX: Float, screenY: Float): Pair<Float, Float>? {
        val frame = viewportFrame()
        if (!frame.contains(screenX, screenY)) return null
        val x = (screenX - frame.left) * (viewportW / frame.width())
        val y = (screenY - frame.top) * (viewportH / frame.height())
        return x to y
    }

    private fun updateMobileControls() {
        inputState.keys.toList().forEach { inputState[it] = 0.0f }
        val controlsEntity = entities.firstOrNull { it.components.has("MobileControls2D") && it.active } ?: return
        val controls = controlsEntity.components.optJSONObject("MobileControls2D") ?: return
        if (!controls.optBoolean("enabled", true)) return
        controlCaptures.keys.retainAll(activePointers.keys)
        for ((pointerId, point) in activePointers) {
            val x = point.first
            val y = point.second
            val stickX = viewportW * controls.optDouble("left_stick_anchor_x", 0.16).toFloat()
            val stickY = viewportH * controls.optDouble("left_stick_anchor_y", 0.78).toFloat()
            val stickRadius = controls.optDouble("left_stick_radius", 86.0).toFloat()
            val capture = controlCaptures[pointerId] ?: captureControl(controls, x, y)
            if (capture != null) controlCaptures[pointerId] = capture
            when (capture) {
                "left_stick" -> {
                    val dx = x - stickX
                    val dy = y - stickY
                    val distance = hypot(dx, dy)
                    if (controls.optBoolean("left_stick_enabled", true) && distance > 1.0f) {
                        val deadzone = controls.optDouble("deadzone", 0.18).toFloat()
                        val normalized = min(1.0f, distance / stickRadius)
                        if (normalized >= deadzone) {
                            val scale = (normalized - deadzone) / max(0.001f, 1.0f - deadzone)
                            inputState["horizontal"] = (dx / distance * scale).coerceIn(-1.0f, 1.0f)
                            inputState["vertical"] = (-dy / distance * scale).coerceIn(-1.0f, 1.0f)
                        }
                    }
                }
                "action_1" -> inputState["action_1"] = 1.0f
                "action_2" -> inputState["action_2"] = 1.0f
            }
        }
    }

    private fun buttonHit(controls: JSONObject, prefix: String, x: Float, y: Float): Boolean {
        if (!controls.optBoolean("${prefix}_enabled", true)) return false
        val cx = viewportW * controls.optDouble("${prefix}_anchor_x", if (prefix == "action_1") 0.84 else 0.72).toFloat()
        val cy = viewportH * controls.optDouble("${prefix}_anchor_y", if (prefix == "action_1") 0.78 else 0.84).toFloat()
        val radius = controls.optDouble("${prefix}_radius", if (prefix == "action_1") 54.0 else 46.0).toFloat() * 1.35f
        return hypot(x - cx, y - cy) <= radius
    }

    private fun captureControl(controls: JSONObject, x: Float, y: Float): String? {
        val stickX = viewportW * controls.optDouble("left_stick_anchor_x", 0.16).toFloat()
        val stickY = viewportH * controls.optDouble("left_stick_anchor_y", 0.78).toFloat()
        val stickRadius = controls.optDouble("left_stick_radius", 86.0).toFloat() * 1.35f
        if (controls.optBoolean("left_stick_enabled", true) && hypot(x - stickX, y - stickY) <= stickRadius) {
            return "left_stick"
        }
        if (buttonHit(controls, "action_1", x, y)) return "action_1"
        if (buttonHit(controls, "action_2", x, y)) return "action_2"
        return null
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

    private fun rebuildEntitiesFromScene() {
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
    }

    private fun runScripts(hookName: String, dt: Float) {
        val bridge = scriptBridge ?: return
        val updated = bridge.runHook(scene, hookName, dt) ?: return
        scene = updated
        rebuildEntitiesFromScene()
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

    private fun updateMovingPlatforms(dt: Float) {
        for (entity in entities) {
            val platform = entity.components.optJSONObject("MovingPlatform2D") ?: continue
            if (!entity.active || !platform.optBoolean("enabled", true)) continue
            val path = platform.optJSONArray("path") ?: continue
            if (path.length() < 2) continue
            val speed = platform.optDouble("speed", 0.0).toFloat()
            if (speed <= 0.0f) continue
            val transform = entity.components.optJSONObject("Transform") ?: continue
            val targetIndex = platform.optInt("_target_index", 1).coerceIn(0, path.length() - 1)
            val target = path.optJSONObject(targetIndex) ?: continue
            val tx = target.optDouble("x", transform.optDouble("x")).toFloat()
            val ty = target.optDouble("y", transform.optDouble("y")).toFloat()
            val x = transform.optDouble("x", 0.0).toFloat()
            val y = transform.optDouble("y", 0.0).toFloat()
            val dx = tx - x
            val dy = ty - y
            val distance = hypot(dx, dy)
            if (distance <= 1.0f) {
                val next = if (targetIndex >= path.length() - 1) {
                    if (platform.optBoolean("loop", true)) 0 else targetIndex
                } else {
                    targetIndex + 1
                }
                platform.put("_target_index", next)
                continue
            }
            val step = min(distance, speed * dt)
            transform.put("x", x + dx / distance * step)
            transform.put("y", y + dy / distance * step)
        }
    }

    private fun updateGameplaySemantics() {
        val players = entities.filter { it.active && (it.tag == "Player" || it.components.has("PlayerController2D")) }
        if (players.isEmpty()) return
        for (player in players) {
            val playerRect = worldRect(player) ?: continue
            for (target in entities.toList()) {
                if (!target.active || target.name == player.name) continue
                val targetRect = worldRect(target) ?: continue
                if (!RectF.intersects(playerRect, targetRect)) continue
                handleCheckpoint(player, target)
                handleHazard(player, target)
                handleKillzone(player, target)
                handleGoal(target)
                handleCollectible(target)
            }
            handleLevelBounds(player)
        }
        rebuildEntitiesFromScene()
    }

    private fun handleCollectible(target: Entity) {
        val collectible = target.components.optJSONObject("Collectible2D") ?: return
        if (!collectible.optBoolean("enabled", true)) return
        if (collectible.optBoolean("destroy_on_collect", true)) {
            removeEntityByName(target.name)
        }
    }

    private fun handleCheckpoint(player: Entity, target: Entity) {
        val checkpoint = target.components.optJSONObject("Checkpoint2D") ?: return
        if (!checkpoint.optBoolean("enabled", true) || !checkpoint.optBoolean("active", true)) return
        activeRespawnName = checkpoint.optString("checkpoint_id", target.name).ifBlank { target.name }
    }

    private fun handleHazard(player: Entity, target: Entity) {
        val hazard = target.components.optJSONObject("Hazard2D") ?: return
        if (!hazard.optBoolean("enabled", true) || !hazard.optBoolean("respawn_on_touch", true)) return
        respawnPlayer(player)
    }

    private fun handleKillzone(player: Entity, target: Entity) {
        val killzone = target.components.optJSONObject("KillZone2D") ?: return
        if (!killzone.optBoolean("enabled", true) || !killzone.optBoolean("respawn_on_touch", true)) return
        respawnPlayer(player)
    }

    private fun handleGoal(target: Entity) {
        val goal = target.components.optJSONObject("Goal2D") ?: return
        if (!goal.optBoolean("enabled", true) || !goal.optBoolean("complete_on_touch", true)) return
        val next = goal.optString("next_scene", "")
        if (next.isNotBlank()) loadScene(next)
    }

    private fun handleLevelBounds(player: Entity) {
        val transform = player.components.optJSONObject("Transform") ?: return
        for (entity in entities) {
            val bounds = entity.components.optJSONObject("LevelBounds2D") ?: continue
            if (!entity.active || !bounds.optBoolean("enabled", true)) continue
            val x = transform.optDouble("x", 0.0).toFloat()
            val y = transform.optDouble("y", 0.0).toFloat()
            val left = bounds.optDouble("left", Float.NEGATIVE_INFINITY.toDouble()).toFloat()
            val right = bounds.optDouble("right", Float.POSITIVE_INFINITY.toDouble()).toFloat()
            val top = bounds.optDouble("top", Float.NEGATIVE_INFINITY.toDouble()).toFloat()
            val bottom = bounds.optDouble("bottom", Float.POSITIVE_INFINITY.toDouble()).toFloat()
            if (x < left) transform.put("x", left)
            if (x > right) transform.put("x", right)
            if (y < top) transform.put("y", top)
            if (y > bottom) respawnPlayer(player)
        }
    }

    private fun respawnPlayer(player: Entity) {
        val respawn = findRespawn() ?: return
        val playerTransform = player.components.optJSONObject("Transform") ?: return
        val respawnTransform = respawn.components.optJSONObject("Transform") ?: return
        playerTransform.put("x", respawnTransform.optDouble("x", playerTransform.optDouble("x")))
        playerTransform.put("y", respawnTransform.optDouble("y", playerTransform.optDouble("y")))
        val rb = player.components.optJSONObject("RigidBody")
        rb?.put("velocity_x", 0.0)
        rb?.put("velocity_y", 0.0)
    }

    private fun findRespawn(): Entity? {
        val wanted = activeRespawnName
        if (!wanted.isNullOrBlank()) {
            entities.firstOrNull {
                val respawn = it.components.optJSONObject("RespawnPoint2D")
                respawn != null && (respawn.optString("spawn_id") == wanted || it.name == wanted)
            }?.let { return it }
        }
        return entities.firstOrNull {
            val respawn = it.components.optJSONObject("RespawnPoint2D")
            it.active && respawn != null && respawn.optBoolean("enabled", true) && respawn.optBoolean("active", true)
        }
    }

    private fun removeEntityByName(name: String) {
        val arr = scene.optJSONArray("entities") ?: return
        for (i in arr.length() - 1 downTo 0) {
            val obj = arr.optJSONObject(i) ?: continue
            if (obj.optString("name") == name) {
                arr.remove(i)
                return
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
        val rect = visualRect(entity) ?: worldRect(entity) ?: return
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

    private fun visualRect(entity: Entity): RectF? {
        val t = entity.components.optJSONObject("Transform") ?: return null
        val sprite = entity.components.optJSONObject("Sprite")
        val animator = entity.components.optJSONObject("Animator")
        val collider = entity.components.optJSONObject("Collider")
        val w = when {
            animator != null -> animator.optDouble("frame_width", 64.0)
            sprite != null -> sprite.optDouble("width", 64.0)
            collider != null -> collider.optDouble("width", 64.0)
            else -> 64.0
        }.toFloat() * t.optDouble("scale_x", 1.0).toFloat()
        val h = when {
            animator != null -> animator.optDouble("frame_height", 64.0)
            sprite != null -> sprite.optDouble("height", 64.0)
            collider != null -> collider.optDouble("height", 64.0)
            else -> 64.0
        }.toFloat() * t.optDouble("scale_y", 1.0).toFloat()
        val x = t.optDouble("x", 0.0).toFloat()
        val y = t.optDouble("y", 0.0).toFloat()
        if (sprite != null && animator == null) {
            val ox = sprite.optDouble("origin_x", 0.5).toFloat()
            val oy = sprite.optDouble("origin_y", 0.5).toFloat()
            return RectF(x - w * ox, y - h * oy, x + w * (1.0f - ox), y + h * (1.0f - oy))
        }
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

    private class ScriptBehaviourBridge(private val context: Context) {
        private var adapter: Any? = null
        private var unavailableLogged = false

        fun runHook(scene: JSONObject, hookName: String, dt: Float): JSONObject? {
            if (!sceneHasScripts(scene)) return null
            val module = adapter ?: loadAdapter() ?: return null
            return try {
                val callAttr = module.javaClass.methods.firstOrNull {
                    it.name == "callAttr" && it.parameterTypes.size == 2
                } ?: return null
                val result = callAttr.invoke(module, "run_hook", arrayOf<Any>(scene.toString(), hookName, dt.toDouble()))
                val text = result?.toString() ?: return null
                JSONObject(text)
            } catch (exc: Exception) {
                Log.e(TAG, "ScriptBehaviourBridge hook failed: $hookName", exc)
                null
            }
        }

        private fun loadAdapter(): Any? {
            return try {
                val pythonClass = Class.forName("com.chaquo.python.Python")
                val isStarted = pythonClass.getMethod("isStarted").invoke(null) as Boolean
                if (!isStarted) {
                    val platformClass = Class.forName("com.chaquo.python.android.AndroidPlatform")
                    val platform = platformClass.getConstructor(Context::class.java).newInstance(context)
                    pythonClass.methods.first { it.name == "start" && it.parameterTypes.size == 1 }.invoke(null, platform)
                }
                val python = pythonClass.getMethod("getInstance").invoke(null)
                val module = python.javaClass.getMethod("getModule", String::class.java).invoke(python, "motor_android_runtime")
                adapter = module
                module
            } catch (exc: Exception) {
                if (!unavailableLogged) {
                    Log.e(TAG, "ScriptBehaviourBridge unavailable. Check Chaquopy runtime.", exc)
                    unavailableLogged = true
                }
                null
            }
        }

        private fun sceneHasScripts(scene: JSONObject): Boolean {
            val arr = scene.optJSONArray("entities") ?: return false
            for (i in 0 until arr.length()) {
                val components = arr.optJSONObject(i)?.optJSONObject("components") ?: continue
                val script = components.optJSONObject("ScriptBehaviour") ?: continue
                if (script.optBoolean("enabled", true)) return true
            }
            return false
        }
    }

    private class SharedRuntimeBridge(private val context: Context) {
        private var module: Any? = null
        private var unavailableLogged = false

        fun create(basePath: String, config: JSONObject): JSONObject? {
            return call("create_shared_runtime", basePath, config.toString())
        }

        fun loadScene(scenePath: String): JSONObject? {
            return call("load_shared_scene", scenePath)
        }

        fun runFrame(dt: Float, pointerState: JSONObject): JSONObject? {
            return call("run_shared_frame", dt.toDouble(), pointerState.toString())
        }

        private fun call(name: String, vararg args: Any): JSONObject? {
            val target = module ?: loadModule() ?: return null
            return try {
                val callAttr = target.javaClass.methods.firstOrNull {
                    it.name == "callAttr" && it.parameterTypes.size == 2
                } ?: return null
                val result = callAttr.invoke(target, name, args as Array<Any>)
                val text = result?.toString() ?: return null
                JSONObject(text)
            } catch (exc: Exception) {
                Log.e(TAG, "SharedRuntimeBridge call failed: $name", exc)
                null
            }
        }

        private fun loadModule(): Any? {
            return try {
                val pythonClass = Class.forName("com.chaquo.python.Python")
                val isStarted = pythonClass.getMethod("isStarted").invoke(null) as Boolean
                if (!isStarted) {
                    val platformClass = Class.forName("com.chaquo.python.android.AndroidPlatform")
                    val platform = platformClass.getConstructor(Context::class.java).newInstance(context)
                    pythonClass.methods.first { it.name == "start" && it.parameterTypes.size == 1 }.invoke(null, platform)
                }
                val python = pythonClass.getMethod("getInstance").invoke(null)
                val loaded = python.javaClass.getMethod("getModule", String::class.java).invoke(python, "motor_android_runtime")
                module = loaded
                loaded
            } catch (exc: Exception) {
                if (!unavailableLogged) {
                    Log.e(TAG, "SharedRuntimeBridge unavailable. Check Chaquopy runtime.", exc)
                    unavailableLogged = true
                }
                null
            }
        }
    }

    private data class CameraState(val x: Float, val y: Float, val offsetX: Float, val offsetY: Float, val zoom: Float)

    companion object {
        private const val TAG = "MotorGame"
        private val ANDROID_RUNTIME_ASSET_PATHS = listOf("runtime_config.json", "game.manifest.json", "levels", "assets", "scripts")
        private val ANDROID_RUNTIME_REQUIRED_ASSET_PATHS = setOf("runtime_config.json", "game.manifest.json", "levels")
    }
}
