package com.finora.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import androidx.core.app.NotificationCompat;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class PaymentNotificationListener extends NotificationListenerService {

    public static final String CHANNEL_ID = "finora_expense_detect";
    private static final Map<String, Long> recentEvents = new HashMap<>();

    // Common payment packages in India
    private static final String[] PAYMENT_PACKAGES = {
        "com.google.android.apps.nbu.paisa.user", // Google Pay
        "com.phonepe.app",                       // PhonePe
        "net.one97.paytm",                       // Paytm
        "com.dreamplug.androidapp",              // CRED
        "in.org.npci.upiapp",                    // BHIM
        "in.amazon.mShop.android.shopping",      // Amazon Pay
        "com.google.android.apps.messaging",     // Google Messages (Bank SMS)
        "com.samsung.android.messaging",        // Samsung Messages
        "com.android.mms"                        // Default SMS
    };

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null || sbn.getPackageName() == null) return;

        // Skip FINORA's own notifications
        if (sbn.getPackageName().equals(getPackageName())) return;

        Bundle extras = sbn.getNotification().extras;
        if (extras == null) return;

        String title = extras.getString(android.app.Notification.EXTRA_TITLE, "");
        CharSequence textSeq = extras.getCharSequence(android.app.Notification.EXTRA_TEXT);
        CharSequence bigTextSeq = extras.getCharSequence(android.app.Notification.EXTRA_BIG_TEXT);

        String text = (bigTextSeq != null) ? bigTextSeq.toString() : (textSeq != null ? textSeq.toString() : "");
        String fullContent = (title + " " + text).toLowerCase();

        // Check if package is a payment app
        boolean isPaymentApp = false;
        for (String pkg : PAYMENT_PACKAGES) {
            if (sbn.getPackageName().contains(pkg)) {
                isPaymentApp = true;
                break;
            }
        }

        // Keywords check
        boolean hasPaymentKeywords = fullContent.contains("paid") ||
                                     fullContent.contains("debited") ||
                                     fullContent.contains("spent") ||
                                     fullContent.contains("sent") ||
                                     fullContent.contains("txn of") ||
                                     fullContent.contains("payment of") ||
                                     fullContent.contains("transferred");

        boolean hasCurrency = fullContent.contains("rs") ||
                              fullContent.contains("inr") ||
                              fullContent.contains("₹");

        if (!isPaymentApp && !(hasPaymentKeywords && hasCurrency)) {
            return;
        }

        // Extract amount
        double amount = extractAmount(title + " " + text);
        if (amount <= 0) return;

        // Extract payee / merchant
        String payee = extractPayee(title + " " + text);
        if (payee == null || payee.trim().isEmpty()) {
            payee = getAppName(sbn.getPackageName());
        }

        // Prevent duplicate alerts within 60 seconds
        String dedupKey = String.format("%.2f_%s", amount, payee.toLowerCase());
        long now = System.currentTimeMillis();
        if (recentEvents.containsKey(dedupKey) && (now - recentEvents.get(dedupKey)) < 60000) {
            return;
        }
        recentEvents.put(dedupKey, now);

        // Show FINORA 1-Tap expense prompt
        showExpenseNotification(amount, payee, getAppName(sbn.getPackageName()));
    }

    private double extractAmount(String raw) {
        Pattern pattern = Pattern.compile("(?:rs\\.?|inr|₹)\\s*([\\d,]+(?:\\.\\d{1,2})?)", Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(raw);
        if (matcher.find()) {
            try {
                String clean = matcher.group(1).replace(",", "");
                return Double.parseDouble(clean);
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
        if (pkg.contains("dreamplug")) return "CRED";
        if (pkg.contains("amazon")) return "Amazon Pay";
        if (pkg.contains("messaging") || pkg.contains("mms")) return "Bank SMS";
        return "UPI";
    }

    private void showExpenseNotification(double amount, String payee, String sourceApp) {
        createNotificationChannel();

        int notifId = (int) (System.currentTimeMillis() % 100000);

        // Action 1: Instant Quick Add without opening app
        Intent addIntent = new Intent(this, PaymentActionReceiver.class);
        addIntent.setAction(PaymentActionReceiver.ACTION_ADD);
        addIntent.putExtra("notif_id", notifId);
        addIntent.putExtra("amount", amount);
        addIntent.putExtra("payee", payee);
        addIntent.putExtra("source_app", sourceApp);

        PendingIntent addPendingIntent = PendingIntent.getBroadcast(
            this, notifId, addIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0)
        );

        // Action 2: Open FINORA App
        Intent openIntent = new Intent(this, MainActivity.class);
        openIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        openIntent.putExtra("quick_amount", amount);
        openIntent.putExtra("quick_payee", payee);

        PendingIntent openPendingIntent = PendingIntent.getActivity(
            this, notifId + 1, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0)
        );

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("🔔 FINORA: ₹" + String.format("%.2f", amount) + " Payment Detected")
            .setContentText("Paid to " + payee + " (" + sourceApp + "). Tap to record into FINORA.")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openPendingIntent)
            .addAction(android.R.drawable.ic_input_add, "⚡ Add to Ledger", addPendingIntent)
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
