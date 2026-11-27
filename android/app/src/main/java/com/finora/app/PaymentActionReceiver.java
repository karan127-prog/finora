package com.finora.app;

import android.app.NotificationManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.webkit.CookieManager;
import android.widget.Toast;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class PaymentActionReceiver extends BroadcastReceiver {

    public static final String ACTION_ADD = "com.finora.app.ACTION_QUICK_ADD";
    private static final String PREFS_NAME = "FinoraPrefs";
    private static final String KEY_SERVER_URL = "server_url";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION_ADD.equals(intent.getAction())) return;

        int notifId = intent.getIntExtra("notif_id", 0);
        double amount = intent.getDoubleExtra("amount", 0);
        String payee = intent.getStringExtra("payee");
        String sourceApp = intent.getStringExtra("source_app");

        // Dismiss notification
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null && notifId != 0) {
            manager.cancel(notifId);
        }

        // Post in background to FINORA server
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        String serverUrl = prefs.getString(KEY_SERVER_URL, MainActivity.DEFAULT_URL);

        new Thread(() -> {
            boolean success = postTransactionToServer(serverUrl, amount, payee, sourceApp);
            new Handler(Looper.getMainLooper()).post(() -> {
                if (success) {
                    Toast.makeText(context, "✅ Recorded ₹" + String.format("%.2f", amount) + " to FINORA (" + payee + ")", Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(context, "FINORA: Open app to confirm ₹" + String.format("%.2f", amount), Toast.LENGTH_SHORT).show();
                }
            });
        }).start();
    }

    private boolean postTransactionToServer(String baseUrl, double amount, String payee, String sourceApp) {
        try {
            if (baseUrl.endsWith("/")) {
                baseUrl = baseUrl.substring(0, baseUrl.length() - 1);
            }
            URL url = new URL(baseUrl + "/api/transactions/quick-add-detected");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; utf-8");
            conn.setRequestProperty("Accept", "application/json");
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(8000);
            conn.setDoOutput(true);

            // Attach user session cookies
            String cookie = CookieManager.getInstance().getCookie(baseUrl);
            if (cookie != null && !cookie.isEmpty()) {
                conn.setRequestProperty("Cookie", cookie);
            }

            String jsonPayload = String.format(
                "{\"amount\": %.2f, \"payee\": \"%s\", \"source_app\": \"%s\", \"payment_method\": \"UPI\"}",
                amount,
                (payee != null ? payee.replace("\"", "\\\"") : "UPI Payment"),
                (sourceApp != null ? sourceApp.replace("\"", "\\\"") : "Payment App")
            );

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = jsonPayload.getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }

            int code = conn.getResponseCode();
            return code >= 200 && code < 300;
        } catch (Exception e) {
            e.printStackTrace();
            return false;
        }
    }
}
