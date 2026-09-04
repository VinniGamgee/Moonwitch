from pathlib import Path

manifest = Path("src/android/app/src/main/AndroidManifest.xml")
manifest_text = manifest.read_text(encoding="utf-8")
old_manifest = '''        <activity
            android:name="org.yuzu.yuzu_emu.activities.EmulationActivity"
            android:theme="@style/Theme.Yuzu.Main"
            android:launchMode="singleTop"
            android:screenOrientation="portrait"
'''
new_manifest = '''        <activity
            android:name="org.yuzu.yuzu_emu.activities.EmulationActivity"
            android:theme="@style/Theme.Yuzu.Main"
            android:launchMode="singleTop"
            android:screenOrientation="sensorLandscape"
'''
if old_manifest not in manifest_text:
    raise SystemExit("EmulationActivity portrait manifest block not found")
manifest.write_text(manifest_text.replace(old_manifest, new_manifest, 1), encoding="utf-8")

activity = Path("src/android/app/src/main/java/org/yuzu/yuzu_emu/activities/EmulationActivity.kt")
activity_text = activity.read_text(encoding="utf-8")
old_activity = "super.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT)"
new_activity = "super.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE)"
if old_activity not in activity_text:
    raise SystemExit("EmulationActivity portrait orientation override not found")
activity.write_text(activity_text.replace(old_activity, new_activity, 1), encoding="utf-8")

print("Frontend remains portrait; EmulationActivity is now sensorLandscape.")
