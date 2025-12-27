[app]
title = monerod UI
package.name = monerodui
package.domain = org.monerodui
source.dir = src
source.include_exts = py,png,jpg,kv,atlas,json,svg,ini,whl,so,java
source.include_patterns = assets/*,screens/**/*.py,services/*.py,utils/*,ui/**/*.kv,monerodui/service.py
source.exclude_dirs = data,.buildozer,tests,.venv,venv,__pycache__
version = 0.1.0

requirements = python3,kivy,https://github.com/kivymd/KivyMD/archive/master.zip,pillow,materialyoucolor,asynckivy,asyncgui,Kivy-Garden,android,setuptools,wheel,plyer,monerod

# Register the service (name:file:foreground)
services = Monerodui:monerodui/service.py:foreground:sticky

presplash.filename = %(source.dir)s/monerodui/assets/splash_logo.png
icon.filename = %(source.dir)s/monerodui/assets/icon.png
orientation = portrait, landscape

android.accept_sdk_license = True
android.presplash_color = #29292a
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,WAKE_LOCK,POST_NOTIFICATIONS,USE_FULL_SCREEN_INTENT,SYSTEM_ALERT_WINDOW
android.archs = arm64-v8a, armeabi-v7a
android.enable_androidx = True
android.private_storage = True
#android.release_artifact = apk

android.gradle_opts = -Xmx8g -XX:MaxMetaspaceSize=3g
android.no_byte_compile_python = True

# Include your Java source
android.add_src = android/java

p4a.local_recipes = android/p4a-recipes

[buildozer]
log_level = 2
warn_on_root = 1
