package com.finora.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;
import android.webkit.CookieManager;
import androidx.core.app.NotificationCompat;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class PaymentNotificationListener extends NotificationListenerService {

    private static final String TAG = "FINORA_TRACKER";
    public static final String CHANNEL_ID = "finora_expense_detect";
    private static final Map<String, Long> recentEvents = new HashMap<>();

    private static final String[] KNOWN_KEYWORDS = {
        "paid", "debited", "spent", "sent", "transfer", "transferred",
        "txn", "transaction", "payment", "successful", "vpa", "upi"
    };

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        Log.d(TAG, "FINORA PaymentNotificationListener service created and active!");
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null || sbn.getPackageName() == null) return;

        // Ignore our own notifications
        if (sbn.getPackageName().equals(getPackageName())) return;

        Bundle extras = sbn.getNotification().extras;
        if (extras == null) return;

        String title = extras.getString(android.app.Notification.EXTRA_TITLE, "");
        CharSequence textSeq = extras.getCharSequence(android.app.Notification.EXTRA_TEXT);
        CharSequence bigTextSeq = extras.getCharSequence(android.app.Notification.EXTRA_BIG_TEXT);

        String text = (bigTextSeq != null) ? bigTextSeq.toString() : (textSeq != null ? textSeq.toString() : "");
        String fullContent = (title + " " + text).toLowerCase();
        String pkg = sbn.getPackageName().toLowerCase();

        Log.d(TAG, "Notification received from [" + pkg + "]: Title=" + title + " | Text=" + text);

        // Check if package is a payment, banking, or SMS app
        boolean isPaymentApp = pkg.contains("paisa") || pkg.contains("nbu") ||
                              pkg.contains("phonepe") || pkg.contains("paytm") ||
                              pkg.contains("dreamplug") || pkg.contains("cred") ||
                              pkg.contains("amazon") || pkg.contains("bhim") ||
                              pkg.contains("messaging") || pkg.contains("mms") ||
                              pkg.contains("bank") || pkg.contains("upi");

        boolean hasPaymentKeywords = false;
        for (String kw : KNOWN_KEYWORDS) {
            if (fullContent.contains(kw)) {
                hasPaymentKeywords = true;
                break;
            }
        }

        boolean hasCurrency = fullContent.contains("rs") ||
                              fullContent.contains("inr") ||
                              fullContent.contains("₹");

        if (!isPaymentApp && !(hasPaymentKeywords && hasCurrency)) {
            return;
        }

        // Extract amount
        double amount = extractAmount(title + " " + text);
        if (amount <= 0) {
            Log.d(TAG, "No valid amount extracted from: " + fullContent);
            return;
        }

        // Extract payee / merchant
        String rawPayee = extractPayee(title + " " + text);
        final String payee = (rawPayee != null && !rawPayee.trim().isEmpty())
            ? rawPayee
            : getAppName(sbn.getPackageName());

        final String sourceApp = getAppName(sbn.getPackageName());
        final double finalAmount = amount;

        // Deduplication guard: ignore exact same amount & payee within 60 seconds
        String dedupKey = String.format("%.2f_%s", finalAmount, payee.toLowerCase());
        long now = System.currentTimeMillis();
        if (recentEvents.containsKey(dedupKey) && (now - recentEvents.get(dedupKey)) < 60000) {
            Log.d(TAG, "Duplicate notification ignored: " + dedupKey);
            return;
        }
        recentEvents.put(dedupKey, now);

        Log.d(TAG, ">>> CAPTURED PAYMENT: ₹" + finalAmount + " to " + payee + " via " + sourceApp);

        // Auto-record to FINORA server immediately in background
        SharedPreferences prefs = getSharedPreferences("FinoraPrefs", Context.MODE_PRIVATE);
        final String serverUrl = prefs.getString("server_url", MainActivity.DEFAULT_URL);

        new Thread(() -> {
            boolean recorded = postTransactionDirectly(serverUrl, finalAmount, payee, sourceApp);
            showExpenseNotification(finalAmount, payee, sourceApp, recorded);
        }).start();
    }

    private double extractAmount(String raw) {
        // Pattern 1: Symbol before amount (₹ 350.00, Rs. 50, INR 1200)
        Pattern p1 = Pattern.compile("(?:rs\\.?|inr|₹)\\s*([\\d,]+(?:\\.\\d{1,2})?)", Pattern.CASE_INSENSITIVE);
        Matcher m1 = p1.matcher(raw);
        if (m1.find()) {
            try {
                return Double.parseDouble(m1.group(1).replace(",", ""));
            } catch (Exception ignored) {}
        }

        // Pattern 2: Amount before symbol (350.00 ₹, 50 Rs)
        Pattern p2 = Pattern.compile("([\\d,]+(?:\\.\\d{1,2})?)\\s*(?:rs\\.?|inr|₹)", Pattern.CASE_INSENSITIVE);
        Matcher m2 = p2.matcher(raw);
        if (m2.find()) {
            try {
                return Double.parseDouble(m2.group(1).replace(",", ""));
            } catch (Exception ignored) {}
        }

        // Pattern 3: Action keywords followed by numbers (paid 50 to, debited 1200)
        Pattern p3 = Pattern.compile("(?:paid|debited|spent|sent|transfer of|payment of)\\s*([\\d,]+(?:\\.\\d{1,2})?)", Pattern.CASE_INSENSITIVE);
        Matcher m3 = p3.matcher(raw);
        if (m3.find()) {
            try {
                return Double.parseDouble(m3.group(1).replace(",", ""));
            } catch (Exception ignored) {}
        }

        return 0;
    }

    private String extractPayee(String raw) {
        Pattern pattern = Pattern.compile("(?:to|at|for|trf to)\\s+([A-Za-z0-9\\s&'.]{2,30}?)(?:\\s+(?:successful|done|via|using|on|ref|upi|a/c|balance|vpa|\\.)|$)", Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(raw);
        if (matcher.find()) {
            String p = matcher.group(1).trim();
            if (!p.equalsIgnoreCase("you") && !p.equalsIgnoreCase("account") && p.length() > 2) {
                return p;
            }
        }
        return "Merchant";
    }

    private String getAppName(String pkg) {
        if (pkg.contains("paisa") || pkg.contains("nbu")) return "Google Pay";
        if (pkg.contains("phonepe")) return "PhonePe";
        if (pkg.contains("paytm")) return "Paytm";
        if (pkg.contains("dreamplug") || pkg.contains("cred")) return "CRED";
        if (pkg.contains("amazon")) return "Amazon Pay";
        if (pkg.contains("bhim")) return "BHIM UPI";
        if (pkg.contains("messaging") || pkg.contains("mms")) return "Bank SMS";
        return "UPI";
    }

    private boolean postTransactionDirectly(String baseUrl, double amount, String payee, String sourceApp) {
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
            Log.d(TAG, "postTransactionDirectly response code: " + code);
            return code >= 200 && code < 300;
        } catch (Exception e) {
            Log.e(TAG, "Failed to auto-post transaction to server: " + e.getMessage());
            return false;
        }
    }

    private void showExpenseNotification(double amount, String payee, String sourceApp, boolean autoRecorded) {
        createNotificationChannel();

        int notifId = (int) (System.currentTimeMillis() % 100000);

        Intent openIntent = new Intent(this, MainActivity.class);
        openIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        openIntent.putExtra("quick_amount", amount);
        openIntent.putExtra("quick_payee", payee);

        PendingIntent openPendingIntent = PendingIntent.getActivity(
            this, notifId, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0)
        );

        String titleText = autoRecorded
            ? "✅ FINORA: ₹" + String.format("%.2f", amount) + " Auto-Recorded"
            : "🔔 FINORA: ₹" + String.format("%.2f", amount) + " Payment Detected";

        String descText = autoRecorded
            ? "Saved for " + payee + " (" + sourceApp + "). Tap to open."
            : "Paid to " + payee + " (" + sourceApp + "). Tap to record into FINORA.";

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(titleText)
            .setContentText(descText)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openPendingIntent)
            .addAction(android.R.drawable.ic_menu_view, "Open FINORA", openPendingIntent);

        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify(notifId, builder.build());
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "FINORA Expense Alerts",
                NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("Instant alerts when payments are made via Google Pay, PhonePe, or Paytm");
            channel.enableVibration(true);

            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }
}
