package com.finora.app;

import android.annotation.SuppressLint;
import android.content.ComponentName;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.TextUtils;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.net.Uri;
import android.widget.Toast;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

public class MainActivity extends AppCompatActivity {

    public static final String DEFAULT_URL = "http://192.168.1.2:5000";
    private static final String PREFS_NAME = "FinoraPrefs";
    private static final String KEY_SERVER_URL = "server_url";

    private WebView webView;
    private SwipeRefreshLayout swipeRefresh;
    private SharedPreferences prefs;
    private String pendingPrefillJs = null;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);

        android.widget.RelativeLayout layout = new android.widget.RelativeLayout(this);

        swipeRefresh = new SwipeRefreshLayout(this);
        webView = new WebView(this);

        // Native app look: Obsidian dark to match app icon palette, zero edge bounce
        webView.setBackgroundColor(0xFF080E17);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);

        swipeRefresh.addView(webView, new SwipeRefreshLayout.LayoutParams(
                SwipeRefreshLayout.LayoutParams.MATCH_PARENT,
                SwipeRefreshLayout.LayoutParams.MATCH_PARENT
        ));

        layout.addView(swipeRefresh);
        setContentView(layout);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setAllowFileAccess(true);
        settings.setRenderPriority(WebSettings.RenderPriority.HIGH);
        settings.setOffscreenPreRaster(true);

        // Enable persistent cookies across app restarts
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (newProgress >= 100) {
                    swipeRefresh.setRefreshing(false);
                }
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                CookieManager.getInstance().flush();
                if (pendingPrefillJs != null) {
                    final String toRun = pendingPrefillJs;
                    view.postDelayed(() -> view.evaluateJavascript(toRun, null), 350);
                    view.postDelayed(() -> view.evaluateJavascript(toRun, null), 1200);
                    pendingPrefillJs = null;
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    showChangeUrlDialog();
                }
            }
        });

        swipeRefresh.setOnRefreshListener(() -> webView.reload());
        swipeRefresh.setColorSchemeColors(0xFF00E599, 0xFF00CC88);

        String currentUrl = prefs.getString(KEY_SERVER_URL, DEFAULT_URL);
        webView.loadUrl(currentUrl);

        // Check permissions and incoming intent
        checkNotificationPermissions();
        checkSmsPermissions();
        handleIncomingIntent(getIntent());

        // Automatically sync recent bank SMS on launch
        if (checkSelfPermission(android.Manifest.permission.READ_SMS) == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            BankSmsReceiver.syncRecentBankSms(this);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || checkSelfPermission(android.Manifest.permission.READ_SMS) == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            BankSmsReceiver.syncRecentBankSms(this);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == 102 && grantResults.length > 0 && grantResults[0] == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            BankSmsReceiver.syncRecentBankSms(this);
        }
    }

    private void checkSmsPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (checkSelfPermission(android.Manifest.permission.RECEIVE_SMS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{
                    android.Manifest.permission.RECEIVE_SMS,
                    android.Manifest.permission.READ_SMS
                }, 102);
            }
        }
    }

    private void checkNotificationPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 101);
            }
        }

        if (!isNotificationListenerEnabled()) {
            boolean askedBefore = prefs.getBoolean("asked_listener_permission", false);
            if (!askedBefore) {
                prefs.edit().putBoolean("asked_listener_permission", true).apply();
                new AlertDialog.Builder(this)
                    .setTitle("⚡ Auto Payment Tracking")
                    .setMessage("FINORA can automatically detect payments from Google Pay, PhonePe, Paytm, and Bank SMS so you can log expenses with 1 tap.\n\nAllow Notification Access for FINORA in the next screen?")
                    .setPositiveButton("Enable Now", (d, w) -> {
                        startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));
                    })
                    .setNegativeButton("Maybe Later", null)
                    .show();
            }
        }
    }

    private boolean isNotificationListenerEnabled() {
        String pkgName = getPackageName();
        final String flat = Settings.Secure.getString(getContentResolver(), "enabled_notification_listeners");
        if (flat != null) {
            final String[] names = flat.split(":");
            for (String name : names) {
                ComponentName cn = ComponentName.unflattenFromString(name);
                if (cn != null && TextUtils.equals(pkgName, cn.getPackageName())) {
                    return true;
                }
            }
        }
        return false;
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIncomingIntent(intent);
    }

    private void handleIncomingIntent(Intent intent) {
        if (intent == null) return;

        // Option A: Quick Add from FINORA Notification
        if (intent.hasExtra("quick_amount")) {
            handleQuickAddIntent(intent);
            return;
        }

        // Option B: "Share to FINORA" from GPay, PhonePe, Paytm, Banking SMS, WhatsApp
        if (Intent.ACTION_SEND.equals(intent.getAction())) {
            handleSharedReceiptIntent(intent);
        }
    }

    private void handleQuickAddIntent(Intent intent) {
        if (intent == null || !intent.hasExtra("quick_amount")) return;

        double amount = intent.getDoubleExtra("quick_amount", 0);
        String payee = intent.getStringExtra("quick_payee");
        if (payee == null || payee.trim().isEmpty()) payee = "UPI Payment";

        final String finalPayee = payee;
        final String js = String.format(Locale.US,
            "(function() { " +
            "  function fill() { " +
            "    if (window.populateQuickAddModal) { " +
            "      window.populateQuickAddModal('expense', %.2f, '%s', 'Captured via notification'); " +
            "      return true; " +
            "    } else if (window.openQuickAddModal) { " +
            "      window.openQuickAddModal('expense'); " +
            "      const t = document.querySelector('#quickAddModal input[name=\"title\"]'); " +
            "      const a = document.querySelector('#quickAddModal input[name=\"amount\"]'); " +
            "      if (t) { t.value = '%s'; t.dispatchEvent(new Event('input', {bubbles:true})); } " +
            "      if (a) { a.value = '%.2f'; a.dispatchEvent(new Event('input', {bubbles:true})); } " +
            "      return true; " +
            "    } " +
            "    return false; " +
            "  } " +
            "  if (!fill()) { " +
            "    let count = 0; " +
            "    const timer = setInterval(() => { count++; if (fill() || count > 12) clearInterval(timer); }, 300); " +
            "  } " +
            "})();",
            amount, finalPayee.replace("'", "\\'"), finalPayee.replace("'", "\\'"), amount
        );

        pendingPrefillJs = js;
        webView.postDelayed(() -> webView.evaluateJavascript(js, null), 800);
    }

    public static class ParsedReceipt {
        public double amount = 0;
        public String payee = "";
        public String type = "expense"; // "expense" or "income"
        public String sourceApp = "Shared Receipt";
    }

    private static boolean isValidPayeeCandidate(String s) {
        if (s == null) return false;
        String t = s.trim();
        if (t.length() < 2 || t.length() > 40) return false;
        if (t.matches("(?i)^(₹|rs\\.?|inr|completed|successful|payment|transaction|date|upi|utr|ref|details|debited|credited|banking|account).*")) return false;
        if (t.matches("^[\\d,.:\\-\\s]+$")) return false;
        return true;
    }

    public static ParsedReceipt parseSharedReceiptText(String text) {
        ParsedReceipt res = new ParsedReceipt();
        if (text == null || text.trim().isEmpty()) return res;

        String raw = text.trim();
        String lower = raw.toLowerCase();

        // 1. Identify Source App
        if (lower.contains("google pay") || lower.contains("gpay")) {
            res.sourceApp = "Google Pay";
        } else if (lower.contains("phonepe")) {
            res.sourceApp = "PhonePe";
        } else if (lower.contains("paytm")) {
            res.sourceApp = "Paytm";
        } else if (lower.contains("cred")) {
            res.sourceApp = "CRED";
        } else if (lower.contains("bhim")) {
            res.sourceApp = "BHIM UPI";
        } else {
            res.sourceApp = "UPI Payment";
        }

        // 2. Determine Income vs Expense
        boolean isIncome = lower.contains("received from") ||
                           lower.contains("credited to") ||
                           lower.contains("credited by") ||
                           lower.contains("received") ||
                           lower.contains("sent you") ||
                           lower.contains("added to your");
        res.type = isIncome ? "income" : "expense";

        // 3. Extract Amount
        Pattern p1 = Pattern.compile("(?:rs\\.?|inr|₹|debited\\s+by|debited\\s+with|credited\\s+by)[\\s\\n]*([\\d,]+(?:\\.\\d{1,2})?)", Pattern.CASE_INSENSITIVE);
        Matcher m1 = p1.matcher(raw);
        if (m1.find()) {
            try {
                res.amount = Double.parseDouble(m1.group(1).replace(",", ""));
            } catch (Exception ignored) {}
        }

        if (res.amount <= 0) {
            Pattern p2 = Pattern.compile("([\\d,]+(?:\\.\\d{1,2})?)[\\s\\n]*(?:rs\\.?|inr|₹)", Pattern.CASE_INSENSITIVE);
            Matcher m2 = p2.matcher(raw);
            if (m2.find()) {
                try {
                    res.amount = Double.parseDouble(m2.group(1).replace(",", ""));
                } catch (Exception ignored) {}
            }
        }

        if (res.amount <= 0) {
            Pattern p3 = Pattern.compile("(?:paid|sent|received|payment\\s+of|amount:?)[\\s\\n]*([\\d,]+(?:\\.\\d{1,2})?)", Pattern.CASE_INSENSITIVE);
            Matcher m3 = p3.matcher(raw);
            if (m3.find()) {
                try {
                    res.amount = Double.parseDouble(m3.group(1).replace(",", ""));
                } catch (Exception ignored) {}
            }
        }

        String[] lines = raw.split("\\r?\\n");
        if (res.amount <= 0) {
            for (String l : lines) {
                String clean = l.trim().replaceAll("^[₹RsINR\\s]+", "").replaceAll("[₹RsINR\\s]+$", "");
                if (clean.matches("^[\\d,]+(\\.\\d{1,2})?$")) {
                    try {
                        double parsed = Double.parseDouble(clean.replace(",", ""));
                        if (parsed > 0 && parsed < 10000000) {
                            res.amount = parsed;
                            break;
                        }
                    } catch (Exception ignored) {}
                }
            }
        }

        // 4. Extract Exact Payee / Merchant / Sender Name
        String detectedName = "";

        for (int i = 0; i < lines.length; i++) {
            String line = lines[i].trim();

            // Standalone Header line: "Paid to", "Payment to", "To:", "Received from"
            if (line.matches("(?i)^(paid\\s+to|payment\\s+to|transfer\\s+to|transferred\\s+to|sent\\s+to|received\\s+from|to:?|from:?)$")) {
                if (i + 1 < lines.length) {
                    String nextLine = lines[i + 1].trim();
                    if (isValidPayeeCandidate(nextLine)) {
                        detectedName = nextLine;
                        break;
                    }
                }
            }

            // Inline Header: "Paid to Ram Kumar" or "To: Vijay Store"
            Matcher mInline = Pattern.compile("(?i)^(?:paid\\s+to|payment\\s+to|transfer\\s+to|transferred\\s+to|sent\\s+to|received\\s+from|to:|from:)\\s+([A-Za-z0-9\\s&'.-]{2,35})").matcher(line);
            if (mInline.find()) {
                String cand = mInline.group(1).trim();
                if (isValidPayeeCandidate(cand)) {
                    detectedName = cand;
                    break;
                }
            }

            // Banking / Merchant label: "Banking Name: XYZ"
            Matcher mBank = Pattern.compile("(?i)(?:banking\\s+name:?|merchant:?)\\s*([A-Za-z0-9\\s&'.-]{2,35})").matcher(line);
            if (mBank.find()) {
                String cand = mBank.group(1).trim();
                if (isValidPayeeCandidate(cand)) {
                    detectedName = cand;
                    break;
                }
            }
        }

        // Fallback: Extract name from UPI handle (e.g. "rohit.sharma@oksbi" -> "Rohit Sharma")
        if (detectedName.isEmpty()) {
            Pattern pUpi = Pattern.compile("(?i)([a-zA-Z0-9.-]{3,25})@(okhdfcbank|okaxis|oksbi|okicici|ybl|ibl|paytm|axl|upi)");
            Matcher mUpi = pUpi.matcher(raw);
            if (mUpi.find()) {
                String u = mUpi.group(1).replace(".", " ").replace("-", " ").trim();
                if (u.length() >= 3) {
                    detectedName = u;
                }
            }
        }

        // Fallback 2: Check first meaningful non-status line
        if (detectedName.isEmpty()) {
            for (String l : lines) {
                String cl = l.trim();
                if (isValidPayeeCandidate(cl) && !cl.matches("(?i).*(success|transaction|completed|debited|credited|ref|utr|google|phonepe|paytm|bank|account|order).*")) {
                    detectedName = cl;
                    break;
                }
            }
        }

        if (detectedName.isEmpty()) {
            detectedName = isIncome ? "UPI Sender" : "UPI Merchant";
        }

        // Clean up unwanted trailing tags
        detectedName = detectedName.replaceAll("(?i)\\b(using|on|via|account|phonepe|gpay|paytm|completed|successful)\\b.*", "").trim();

        // Format user-facing Title clearly indicating direction ("Paid to X" or "Received from Y")
        if (isIncome) {
            res.payee = detectedName.toLowerCase().startsWith("received from") ? detectedName : "Received from " + detectedName;
        } else {
            res.payee = detectedName.toLowerCase().startsWith("paid to") ? detectedName : "Paid to " + detectedName;
        }

        return res;
    }

    private void handleSharedReceiptIntent(Intent intent) {
        String sharedText = intent.getStringExtra(Intent.EXTRA_TEXT);
        if (sharedText == null || sharedText.trim().isEmpty()) {
            CharSequence extraSubject = intent.getCharSequenceExtra(Intent.EXTRA_SUBJECT);
            if (extraSubject != null) sharedText = extraSubject.toString();
        }

        // Case 1: Plain text or receipt text is directly present
        if (sharedText != null && !sharedText.trim().isEmpty()) {
            processSharedTextAndPrefill(sharedText);
            return;
        }

        // Case 2: Intent with image / stream or other share format
        Uri imageUri = null;
        if (intent.hasExtra(Intent.EXTRA_STREAM)) {
            try {
                imageUri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            } catch (Exception ignored) {}
        }
        if (imageUri == null && intent.getClipData() != null && intent.getClipData().getItemCount() > 0) {
            imageUri = intent.getClipData().getItemAt(0).getUri();
        }
        if (imageUri == null) {
            imageUri = intent.getData();
        }

        if (imageUri != null) {
            try {
                Toast.makeText(this, "⚡ Scanning receipt image...", Toast.LENGTH_SHORT).show();
                InputImage image = InputImage.fromFilePath(this, imageUri);
                TextRecognizer recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
                recognizer.process(image)
                    .addOnSuccessListener(visionText -> {
                        String ocrText = visionText.getText();
                        if (ocrText != null && !ocrText.trim().isEmpty()) {
                            processSharedTextAndPrefill(ocrText);
                        } else {
                            openFallbackQuickAdd();
                        }
                    })
                    .addOnFailureListener(e -> openFallbackQuickAdd());
                return;
            } catch (Exception e) {
                openFallbackQuickAdd();
                return;
            }
        }

        // Fallback if no text and no image Uri
        openFallbackQuickAdd();
    }

    private void processSharedTextAndPrefill(String text) {
        ParsedReceipt receipt = parseSharedReceiptText(text);
        if (receipt.amount <= 0 && (receipt.payee == null || receipt.payee.isEmpty())) {
            openFallbackQuickAdd();
            return;
        }

        String prefix = "income".equals(receipt.type) ? "+" : "-";
        Toast.makeText(this, "⚡ FINORA: " + receipt.payee + " (" + prefix + "₹" + String.format(Locale.US, "%.2f", receipt.amount) + ")", Toast.LENGTH_LONG).show();

        final ParsedReceipt r = receipt;
        final String js = String.format(Locale.US,
            "(function() { " +
            "  function fill() { " +
            "    if (window.populateQuickAddModal) { " +
            "      window.populateQuickAddModal('%s', %.2f, '%s', 'Shared via %s'); " +
            "      return true; " +
            "    } else if (window.openQuickAddModal) { " +
            "      window.openQuickAddModal('%s'); " +
            "      const t = document.querySelector('#quickAddModal input[name=\"title\"]'); " +
            "      const a = document.querySelector('#quickAddModal input[name=\"amount\"]'); " +
            "      const d = document.querySelector('#quickAddModal input[name=\"description\"]'); " +
            "      if (t) { t.value = '%s'; t.dispatchEvent(new Event('input', {bubbles:true})); } " +
            "      if (a) { a.value = '%.2f'; a.dispatchEvent(new Event('input', {bubbles:true})); } " +
            "      if (d) { d.value = 'Shared via %s'; d.dispatchEvent(new Event('input', {bubbles:true})); } " +
            "      return true; " +
            "    } " +
            "    return false; " +
            "  } " +
            "  if (!fill()) { " +
            "    let count = 0; " +
            "    const timer = setInterval(() => { count++; if (fill() || count > 15) clearInterval(timer); }, 300); " +
            "  } " +
            "})();",
            r.type,
            r.amount,
            r.payee.replace("'", "\\'"),
            r.sourceApp,
            r.type,
            r.payee.replace("'", "\\'"),
            r.amount,
            r.sourceApp
        );

        pendingPrefillJs = js;

        // Try immediate execution if page is ready
        webView.post(() -> webView.evaluateJavascript(js, null));
        webView.postDelayed(() -> webView.evaluateJavascript(js, null), 800);
        webView.postDelayed(() -> webView.evaluateJavascript(js, null), 1600);
    }

    private void openFallbackQuickAdd() {
        webView.postDelayed(() -> {
            String js = "if (window.openQuickAddModal) { window.openQuickAddModal('expense'); }";
            webView.evaluateJavascript(js, null);
        }, 1000);
    }

    private void showChangeUrlDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("FINORA Server Connection");
        builder.setMessage("Could not connect to: " + webView.getUrl() + "\n\nEnter your Render live URL or PC IP:");

        final EditText input = new EditText(this);
        input.setHint("e.g. https://finora.onrender.com or http://192.168.1.2:5000");
        input.setText(prefs.getString(KEY_SERVER_URL, DEFAULT_URL));
        builder.setView(input);

        builder.setPositiveButton("Connect", (dialog, which) -> {
            String newUrl = input.getText().toString().trim();
            if (!newUrl.isEmpty()) {
                if (!newUrl.startsWith("http://") && !newUrl.startsWith("https://")) {
                    newUrl = "https://" + newUrl;
                }
                prefs.edit().putString(KEY_SERVER_URL, newUrl).apply();
                webView.loadUrl(newUrl);
            }
        });

        builder.setNegativeButton("Retry", (dialog, which) -> webView.reload());
        builder.show();
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onStop() {
        super.onStop();
        CookieManager.getInstance().flush();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }
}
