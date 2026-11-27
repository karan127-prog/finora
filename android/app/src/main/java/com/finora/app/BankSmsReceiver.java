package com.finora.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.telephony.SmsMessage;
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

public class BankSmsReceiver extends BroadcastReceiver {

    private static final String TAG = "FINORA_SMS_TRACKER";
    public static final String CHANNEL_ID = "finora_bank_sms";
    private static final Map<String, Long> recentSmsEvents = new HashMap<>();

    // Strict Security List: If SMS contains ANY of these keywords, it is 100% IGNORED immediately!
    private static final String[] BLOCKED_SECURITY_WORDS = {
        "otp", "verification", "security code", "secret", "password",
        "do not share", "never share", "one time password", "login code"
    };

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !"android.provider.Telephony.SMS_RECEIVED".equals(intent.getAction())) {
            return;
        }

        Bundle bundle = intent.getExtras();
        if (bundle == null) return;

        Object[] pdus = (Object[]) bundle.get("pdus");
        String format = bundle.getString("format");
        if (pdus == null || pdus.length == 0) return;

        StringBuilder fullBody = new StringBuilder();
        String sender = "";

        for (Object pdu : pdus) {
            SmsMessage message;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                message = SmsMessage.createFromPdu((byte[]) pdu, format);
            } else {
                message = SmsMessage.createFromPdu((byte[]) pdu);
            }
            if (message != null) {
                if (sender.isEmpty()) {
                    sender = message.getDisplayOriginatingAddress();
                }
                fullBody.append(message.getMessageBody());
            }
        }

        processSms(context, sender, fullBody.toString(), true);
    }

    public static void syncRecentBankSms(Context context) {
        new Thread(() -> {
            try {
                Uri uri = Uri.parse("content://sms/inbox");
                Cursor cursor = context.getContentResolver().query(
                    uri,
                    new String[]{"address", "body", "date"},
                    null,
                    null,
                    "date DESC LIMIT 25"
                );
                if (cursor != null) {
                    while (cursor.moveToNext()) {
                        String address = cursor.getString(0);
                        String body = cursor.getString(1);
                        processSms(context, address, body, false);
                    }
                    cursor.close();
                }
            } catch (Exception e) {
                Log.e(TAG, "Error syncing past SMS inbox: " + e.getMessage());
            }
        }).start();
    }

    public static void processSms(Context context, String sender, String rawSms, boolean notifyUser) {
        if (rawSms == null || rawSms.trim().isEmpty()) return;

        String lowerSms = rawSms.toLowerCase();

        // 1. STRICT ZERO-OTP FIREWALL: Never touch OTPs or sensitive codes!
        for (String blocked : BLOCKED_SECURITY_WORDS) {
            if (lowerSms.contains(blocked)) {
                return;
            }
        }

        // 2. Check for DEBIT (Expense) or CREDIT (Income)
        boolean isDebit = lowerSms.contains("debited") ||
                          lowerSms.contains("spent") ||
                          lowerSms.contains("transferred") ||
                          lowerSms.contains("paid") ||
                          lowerSms.contains("withdrawn") ||
                          lowerSms.contains("purchase of") ||
                          lowerSms.contains("trf to");

        boolean isCredit = lowerSms.contains("credited") ||
                           lowerSms.contains("received") ||
                           lowerSms.contains("deposited") ||
                           lowerSms.contains("cr to") ||
                           lowerSms.contains("refund") ||
                           lowerSms.contains("cashback");

        if (!isDebit && !isCredit) {
            return;
        }

        final String txType = isCredit ? "income" : "expense";

        // 3. Extract amount
        double amount = extractAmount(rawSms);
        if (amount <= 0) return;

        // 4. Extract merchant / payee
        String payee = extractPayee(rawSms, isCredit);
        if (payee == null || payee.trim().isEmpty()) {
            payee = extractBankName(sender);
        }

        String bankName = extractBankName(sender);

        // Deduplication guard: ignore exact duplicate within 30 seconds
        String dedupKey = String.format("%s_%.2f_%s", txType, amount, payee.toLowerCase());
        long now = System.currentTimeMillis();
        if (recentSmsEvents.containsKey(dedupKey) && (now - recentSmsEvents.get(dedupKey)) < 30000) {
            return;
        }
        recentSmsEvents.put(dedupKey, now);

        Log.d(TAG, ">>> MATCHED BANK SMS: [" + txType.toUpperCase() + "] ₹" + amount + " | " + payee + " (" + bankName + ")");

        // 5. Post to FINORA server
        SharedPreferences prefs = context.getSharedPreferences("FinoraPrefs", Context.MODE_PRIVATE);
        final String serverUrl = prefs.getString("server_url", MainActivity.DEFAULT_URL);
        final double finalAmount = amount;
        final String finalPayee = payee;
        final String finalBank = bankName;

        new Thread(() -> {
            boolean recorded = postTransactionDirectly(serverUrl, finalAmount, finalPayee, finalBank, txType);
            if (notifyUser) {
                showBankSmsNotification(context, finalAmount, finalPayee, finalBank, txType, recorded);
            }
        }).start();
    }

    private static double extractAmount(String raw) {
        // Pattern 1: Action keywords with amount (debited by 10.00, debited with 500, spent by 250, credited by 100)
        Pattern p1 = Pattern.compile("(?:debited\\s+by|debited\\s+with|debited\\s+for|spent\\s+by|spent\\s+of|credited\\s+by|credited\\s+with|received|purchase\\s+of|rs\\.?|inr|₹)\\s*([\\d,]+(?:\\.\\d{1,2})?)", Pattern.CASE_INSENSITIVE);
        Matcher m1 = p1.matcher(raw);
        if (m1.find()) {
            try {
                return Double.parseDouble(m1.group(1).replace(",", ""));
            } catch (Exception ignored) {}
        }

        // Pattern 2: Amount followed by currency symbol (500.00 Rs, 10 ₹)
        Pattern p2 = Pattern.compile("([\\d,]+(?:\\.\\d{1,2})?)\\s*(?:rs\\.?|inr|₹)", Pattern.CASE_INSENSITIVE);
        Matcher m2 = p2.matcher(raw);
        if (m2.find()) {
            try {
                return Double.parseDouble(m2.group(1).replace(",", ""));
            } catch (Exception ignored) {}
        }

        // Pattern 3: General fallback
        Pattern p3 = Pattern.compile("(?:paid|debited|spent|sent|trf)\\s*([\\d,]+(?:\\.\\d{1,2})?)", Pattern.CASE_INSENSITIVE);
        Matcher m3 = p3.matcher(raw);
        if (m3.find()) {
            try {
                return Double.parseDouble(m3.group(1).replace(",", ""));
            } catch (Exception ignored) {}
        }

        return 0;
    }

    private static String extractPayee(String raw, boolean isCredit) {
        String regex = isCredit
            ? "(?:from|by|trf\\s+from|received\\s+from)\\s+([A-Za-z0-9\\s&'.-]{2,35}?)(?:\\s+(?:Refno|ref|on\\s+date|avl|balance|val|upi|\\.)|$)"
            : "(?:trf\\s+to|to|at|for|vpa)\\s+([A-Za-z0-9\\s&'.-]{2,35}?)(?:\\s+(?:Refno|ref|on\\s+date|avl|balance|val|upi|\\.)|$)";

        Pattern pattern = Pattern.compile(regex, Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(raw);
        if (matcher.find()) {
            String p = matcher.group(1).trim();
            if (!p.equalsIgnoreCase("you") && !p.equalsIgnoreCase("account") && p.length() > 2) {
                return p;
            }
        }
        return isCredit ? "Income Transfer" : "Bank Transaction";
    }

    private static String extractBankName(String sender) {
        if (sender == null) return "Bank SMS";
        String s = sender.toUpperCase();
        if (s.contains("SBI")) return "State Bank of India";
        if (s.contains("HDFC")) return "HDFC Bank";
        if (s.contains("ICICI")) return "ICICI Bank";
        if (s.contains("AXIS")) return "Axis Bank";
        if (s.contains("KOTAK")) return "Kotak Bank";
        if (s.contains("PNB")) return "PNB Bank";
        if (s.contains("BOB")) return "Bank of Baroda";
        if (s.contains("CANARA") || s.contains("CNRB")) return "Canara Bank";
        if (s.contains("PAYTM")) return "Paytm Bank";
        if (s.contains("IDFC")) return "IDFC First Bank";
        return "Bank SMS";
    }

    private static boolean postTransactionDirectly(String baseUrl, double amount, String payee, String bankName, String txType) {
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
                "{\"amount\": %.2f, \"payee\": \"%s\", \"source_app\": \"%s\", \"payment_method\": \"Bank UPI\", \"type\": \"%s\"}",
                amount,
                (payee != null ? payee.replace("\"", "\\\"") : "Bank Transfer"),
                bankName,
                txType
            );

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = jsonPayload.getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }

            int code = conn.getResponseCode();
            Log.d(TAG, "postTransactionDirectly code: " + code);
            return code >= 200 && code < 300;
        } catch (Exception e) {
            Log.e(TAG, "Failed to auto-post bank SMS transaction: " + e.getMessage());
            return false;
        }
    }

    private static void showBankSmsNotification(Context context, double amount, String payee, String bankName, String txType, boolean autoRecorded) {
        createNotificationChannel(context);

        int notifId = (int) (System.currentTimeMillis() % 100000);

        Intent openIntent = new Intent(context, MainActivity.class);
        openIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        openIntent.putExtra("quick_amount", amount);
        openIntent.putExtra("quick_payee", payee);

        PendingIntent openPendingIntent = PendingIntent.getActivity(
            context, notifId, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0)
        );

        String isInc = "income".equals(txType);
        String prefix = isInc ? "+" : "-";
        String verb = isInc ? "Received" : "Debit Saved";

        String titleText = "🏦 FINORA: " + prefix + "₹" + String.format("%.2f", amount) + " " + verb;
        String descText = isInc ? "From " + payee + " (" + bankName + "). Tap to view." : "To " + payee + " (" + bankName + "). Tap to view.";

        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(titleText)
            .setContentText(descText)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openPendingIntent)
            .addAction(android.R.drawable.ic_menu_view, "Open FINORA", openPendingIntent);

        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify(notifId, builder.build());
        }
    }

    private static void createNotificationChannel(Context context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "FINORA Bank SMS Alerts",
                NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("Automatic alerts for bank debit messages");
            channel.enableVibration(true);

            NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }
}
