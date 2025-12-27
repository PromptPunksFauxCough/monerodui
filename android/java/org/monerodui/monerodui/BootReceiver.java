package org.monerodui.monerodui;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import java.io.FileWriter;
import java.io.PrintWriter;

public class BootReceiver extends BroadcastReceiver {

    private void log(String msg) {
        try {
            PrintWriter pw = new PrintWriter(new FileWriter("/storage/emulated/0/Download/boot_receiver.log", true));
            pw.println(System.currentTimeMillis() + ": " + msg);
            pw.close();
        } catch (Exception e) {}
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }

        log("BOOT_COMPLETED received");

        SharedPreferences prefs = context.getApplicationContext()
            .getSharedPreferences("monerodui", Context.MODE_PRIVATE);
        boolean enabled = prefs.getBoolean("enable_boot", false);
        log("enable_boot=" + enabled);

        if (!enabled) {
            return;
        }

        if (Settings.canDrawOverlays(context)) {
            log("Overlay permission granted, launching via overlay");
            launchViaOverlay(context);
        } else {
            log("No overlay permission, falling back to notification");
            showFallbackNotification(context);
        }
    }

    private void launchViaOverlay(Context context) {
        WindowManager wm = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        View overlay = new View(context);

        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
            1, 1,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
            PixelFormat.TRANSLUCENT
        );
        params.gravity = Gravity.TOP | Gravity.START;

        try {
            wm.addView(overlay, params);
            log("Overlay added");
        } catch (Exception e) {
            log("Overlay failed: " + e.getMessage());
            showFallbackNotification(context);
            return;
        }

        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            try {
                Intent activityIntent = new Intent();
                activityIntent.setComponent(new ComponentName(
                    "org.monerodui.monerodui",
                    "org.kivy.android.PythonActivity"
                ));
                activityIntent.setAction(Intent.ACTION_MAIN);
                activityIntent.addCategory(Intent.CATEGORY_LAUNCHER);
                activityIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                context.startActivity(activityIntent);
                log("Activity launched");
            } catch (Exception e) {
                log("Activity launch failed: " + e.getMessage());
                showFallbackNotification(context);
            }

            try {
                wm.removeView(overlay);
                log("Overlay removed");
            } catch (Exception e) {
                log("Overlay removal failed: " + e.getMessage());
            }
        }, 200);
    }

    private void showFallbackNotification(Context context) {
        String channelId = "boot_fallback";
        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                channelId, "Boot Notification", NotificationManager.IMPORTANCE_HIGH);
            channel.setDescription("Tap to open monerod UI");
            nm.createNotificationChannel(channel);
        }

        Intent activityIntent = new Intent();
        activityIntent.setComponent(new ComponentName(
            "org.monerodui.monerodui",
            "org.kivy.android.PythonActivity"
        ));
        activityIntent.setAction(Intent.ACTION_MAIN);
        activityIntent.addCategory(Intent.CATEGORY_LAUNCHER);
        activityIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);

        PendingIntent pendingIntent = PendingIntent.getActivity(
            context, 0, activityIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder = new Notification.Builder(context, channelId);
        } else {
            builder = new Notification.Builder(context);
        }

        Notification notification = builder
            .setContentTitle("monerod UI")
            .setContentText("Tap to open")
            .setSmallIcon(context.getApplicationInfo().icon)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build();

        nm.notify(1002, notification);
        log("Fallback notification posted (1002)");
    }
}
