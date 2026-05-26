package {{APPLICATION_ID}}

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import android.content.res.AssetManager
import android.util.Log

class MainActivity : AppCompatActivity() {
    companion object {
        private const val TAG = "MotorGame"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        Log.i(TAG, "MotorVideojuegosIA - Game starting")
        Log.i(TAG, "Loading assets from: assets/")

        try {
            val assets: AssetManager = this.assets
            val files = assets.list("")
            Log.i(TAG, "Available assets: ${files?.joinToString(", ")}")
        } catch (e: Exception) {
            Log.e(TAG, "Error loading assets", e)
        }
    }
}
