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
import android.util.Log;
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
        if (t.matches("(?i)^(?:₹|\\u20B9|rs\\.?|inr|completed|successful|success|payment|transaction|date|upi|utr|ref|details|debited|deducted|deduction|credited|banking|account|balance|avail|avl|total|bill|order|paid|sent|transfer|money|state\\s+bank|bank|hdfc|icici|axis|sbi|pnb|kotak|\\d).*")) return false;
        if (t.matches("^[\\d,.:\\-\\s/]+$")) return false;
        return true;
    }

    public static ParsedReceipt parseSharedReceiptText(String text) {
        ParsedReceipt res = new ParsedReceipt();
        if (text == null || text.trim().isEmpty()) return res;

        String raw = text.replace('\u00A0', ' ').replace('\u200b', ' ').trim();
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

        // Type defaults to expense; user can manually select Income or Expense in modal
        res.type = "expense";

        String[] lines = raw.split("\\r?\\n");

        // 2. EXTRACT NAME (kisne payment ki hai ya kisko payment ki hai)
        String detectedName = "";

        // Strategy 1: Standalone Header line (PhonePe, GPay, Paytm)
        // e.g. "Transfer to" \n "Ramesh Kumar"
        //      "Paid to" \n "Vijay Store"
        //      "Received from" \n "Amit Verma"
        //      "Paid successfully to" \n "Sharma Bakers"
        for (int i = 0; i < lines.length; i++) {
            String l = lines[i].trim();
            if (l.matches("(?i)^(?:paid\\s+to|paid\\s+successfully\\s+to|transfer\\s+to|transferred\\s+to|received\\s+from|payment\\s+to|sent\\s+to|to:?|from:?)$")) {
                if (i + 1 < lines.length) {
                    String cand = lines[i + 1].trim();
                    if (isValidPayeeCandidate(cand)) {
                        detectedName = cand;
                        break;
                    }
                }
            }
        }

        // Strategy 2: Inline Header (e.g. "Paid to Ramesh Kumar", "Transfer to Vijay", "To: Amit")
        if (detectedName.isEmpty()) {
            for (String l : lines) {
                Matcher m = Pattern.compile("(?i)^(?:paid\\s+to|paid\\s+successfully\\s+to|transfer\\s+to|transferred\\s+to|received\\s+from|payment\\s+to|sent\\s+to|to:|from:)\\s+([A-Za-z0-9\\s&'.-]{2,35})").matcher(l.trim());
                if (m.find()) {
                    String cand = m.group(1).trim();
                    if (isValidPayeeCandidate(cand)) {
                        detectedName = cand;
                        break;
                    }
                }
            }
        }

        // Strategy 3: "Name paid you" or "Name sent you"
        if (detectedName.isEmpty()) {
            Matcher mYou = Pattern.compile("(?i)([A-Za-z0-9&'.-][A-Za-z0-9\\s&'.-]{1,30}?)\\s+(?:paid\\s+you|sent\\s+you)").matcher(raw);
            if (mYou.find()) {
                String cand = mYou.group(1).trim();
                if (isValidPayeeCandidate(cand)) {
                    detectedName = cand;
                }
            }
        }

        // Strategy 4: Bank SMS (e.g. "transfer to UPI/123/Ramesh", "to VPA rohit@upi")
        if (detectedName.isEmpty()) {
            Matcher mSms = Pattern.compile("(?i)(?:towards\\s+upi/|by\\s+upi:\\s*|to\\s+(?:vpa\\s+)?|towards\\s+)([A-Za-z0-9\\s&'.-]{2,30})").matcher(raw);
            if (mSms.find()) {
                String cand = mSms.group(1).split("/")[0].split("@")[0].trim();
                if (isValidPayeeCandidate(cand)) {
                    detectedName = cand;
                }
            }
        }

        // Strategy 5: Banking / Merchant Name label
        if (detectedName.isEmpty()) {
            for (String l : lines) {
                Matcher mBank = Pattern.compile("(?i)(?:banking\\s+name:?|merchant:?)\\s*([A-Za-z0-9\\s&'.-]{2,35})").matcher(l.trim());
                if (mBank.find()) {
                    String cand = mBank.group(1).trim();
                    if (isValidPayeeCandidate(cand)) {
                        detectedName = cand;
                        break;
                    }
                }
            }
        }

        // Strategy 6: UPI handle prefix (e.g. rohit.sharma@okaxis -> Rohit Sharma)
        if (detectedName.isEmpty()) {
            Matcher mUpi = Pattern.compile("(?i)([a-zA-Z0-9.-]{3,25})@(okhdfcbank|okaxis|oksbi|okicici|ybl|ibl|paytm|axl|upi)").matcher(raw);
            if (mUpi.find()) {
                String u = mUpi.group(1).replace(".", " ").replace("-", " ").trim();
                if (u.length() >= 3 && isValidPayeeCandidate(u)) {
                    detectedName = u;
                }
            }
        }

        // Clean Name: remove prefixes and trailing noisy words
        if (!detectedName.isEmpty()) {
            detectedName = detectedName.replaceAll("(?i)^(?:paid\\s+to|paid\\s+successfully\\s+to|transfer\\s+to|transferred\\s+to|received\\s+from|payment\\s+to|sent\\s+to|to|from)\\s+", "").trim();
            detectedName = detectedName.replaceAll("(?i)\\b(bal|balance|avl|avail|using|on|via|account|phonepe|gpay|paytm|completed|debited|deducted|successful)\\b.*", "").trim();
            detectedName = detectedName.replaceAll("^[\\s.,:-]+|[\\s.,:-]+$", "");
        }

        // res.payee is strictly the Person / Merchant Name alone
        res.payee = detectedName;

        // 3. EXTRACT AMOUNT
        double detectedAmount = 0.0;

        // Rule A: Explicit currency symbol ₹ / Rs / INR with number (avoiding balance lines)
        for (String l : lines) {
            String lc = l.trim();
            if (Pattern.compile("(?i)\\b(bal|balance|avail|avl|acct|a/c)\\b").matcher(lc).find() &&
                !Pattern.compile("(?i)\\b(debited|deducted|paid|credited)\\b").matcher(lc).find()) {
                continue;
            }
            Matcher m = Pattern.compile("(?:₹|\\u20B9|rs\\.?|inr)[ \\t:]*([0-9,]+(?:\\.[0-9]{1,2})?)", Pattern.CASE_INSENSITIVE).matcher(lc);
            if (m.find()) {
                try {
                    double val = Double.parseDouble(m.group(1).replace(",", ""));
                    if (val > 0 && val < 10000000) {
                        detectedAmount = val;
                        break;
                    }
                } catch (Exception ignored) {}
            }
        }

        // Rule B: ₹ / Rs / INR on one line, digits on next line
        if (detectedAmount <= 0) {
            for (int i = 0; i < lines.length - 1; i++) {
                String cur = lines[i].trim();
                if (cur.matches("(?i)^(?:₹|\\u20B9|rs\\.?|inr)$")) {
                    String nxt = lines[i + 1].trim().replace(",", "");
                    if (nxt.matches("^[0-9]+(\\.[0-9]{1,2})?$")) {
                        try {
                            double val = Double.parseDouble(nxt);
                            if (val > 0 && val < 10000000) {
                                detectedAmount = val;
                                break;
                            }
                        } catch (Exception ignored) {}
                    }
                }
            }
        }

        // Rule C: Action word near number (debited by Rs 500, paid 500, transfer of 1,200)
        if (detectedAmount <= 0) {
            for (String l : lines) {
                String lc = l.trim();
                if (Pattern.compile("(?i)\\b(bal|balance|avail|avl)\\b").matcher(lc).find() &&
                    !Pattern.compile("(?i)\\b(debited|deducted|paid|credited)\\b").matcher(lc).find()) {
                    continue;
                }
                Matcher m = Pattern.compile("(?i)(?:debited\\s*(?:by|for|with|of)?|deducted\\s*(?:by|for|with|of)?|paid|transfer\\s*(?:of)?|received|credited)[ \\t:]*(?:rs\\.?|inr|₹|\\u20B9)?[ \\t]*([0-9,]+(?:\\.[0-9]{1,2})?)").matcher(lc);
                if (m.find()) {
                    try {
                        double val = Double.parseDouble(m.group(1).replace(",", ""));
                        if (val > 0 && val < 10000000) {
                            detectedAmount = val;
                            break;
                        }
                    } catch (Exception ignored) {}
                }
            }
        }

        // Rule D: Standalone number on the line immediately below the Payee name (common in PhonePe when ₹ is unread)
        if (detectedAmount <= 0 && !res.payee.isEmpty()) {
            for (int i = 0; i < lines.length - 1; i++) {
                if (lines[i].toLowerCase().contains(res.payee.toLowerCase())) {
                    String nxt = lines[i + 1].trim().replace(",", "").replace("₹", "").replaceAll("(?i)rs\\.?", "").trim();
                    if (nxt.matches("^[0-9]+(\\.[0-9]{1,2})?$")) {
                        try {
                            double val = Double.parseDouble(nxt);
                            if (val > 0 && val < 10000000) {
                                detectedAmount = val;
                                break;
                            }
                        } catch (Exception ignored) {}
                    }
                }
            }
        }

        // Rule E: Amount followed by currency symbol (500 ₹, 1250.00 Rs)
        if (detectedAmount <= 0) {
            for (String l : lines) {
                String lc = l.trim();
                if (Pattern.compile("(?i)\\b(bal|balance|avail|avl)\\b").matcher(lc).find()) continue;
                Matcher m = Pattern.compile("([0-9,]+(?:\\.[0-9]{1,2})?)[ \\t]*(?:₹|\\u20B9|rs\\.?|inr)", Pattern.CASE_INSENSITIVE).matcher(lc);
                if (m.find()) {
                    try {
                        double val = Double.parseDouble(m.group(1).replace(",", ""));
                        if (val > 0 && val < 10000000) {
                            detectedAmount = val;
                            break;
                        }
                    } catch (Exception ignored) {}
                }
            }
        }

        // Rule F: Any standard 2-decimal currency amount (e.g. 500.00, 1250.50)
        if (detectedAmount <= 0) {
            Matcher mDec = Pattern.compile("\\b([0-9,]+\\.[0-9]{2})\\b").matcher(raw);
            while (mDec.find()) {
                try {
                    double val = Double.parseDouble(mDec.group(1).replace(",", ""));
                    int start = Math.max(0, mDec.start() - 20);
                    String prefix = raw.substring(start, mDec.start());
                    if (!Pattern.compile("(?i)\\b(bal|balance|avail|avl)\\b").matcher(prefix).find() && val > 0 && val < 10000000) {
                        detectedAmount = val;
                        break;
                    }
                } catch (Exception ignored) {}
            }
        }

        // Rule G: Standalone number on a clean line (e.g. '500')
        if (detectedAmount <= 0) {
            for (String l : lines) {
                if (Pattern.compile("(?i)(?:bal|balance|avail|avl|utr|txn|id|ref|date|time|pm|am|\\*\\*|xxxx|debited\\s+from|credited\\s+to|a/c|account|phonepe|gpay|bank)").matcher(l).find()) {
                    continue;
                }
                String clean = l.replaceAll("^[^0-9]+", "").replaceAll("[^0-9.]+$", "").trim();
                if (clean.matches("^[0-9,]+(\\.[0-9]{1,2})?$")) {
                    try {
                        double val = Double.parseDouble(clean.replace(",", ""));
                        if (val >= 2023 && val <= 2030 && !clean.contains(".")) {
                            continue;
                        }
                        if (clean.replace(",", "").split("\\.")[0].length() > 7) {
                            continue;
                        }
                        if (val > 0 && val < 10000000) {
                            detectedAmount = val;
                            break;
                        }
                    } catch (Exception ignored) {}
                }
            }
        }

        res.amount = detectedAmount;

        Log.i("FinoraOCR", "Raw OCR:\n" + raw);
        Log.i("FinoraOCR", "Extracted -> name=" + res.payee + ", amount=" + res.amount);

        return res;
    }

    private void handleSharedReceiptIntent(Intent intent) {
        String sharedText = intent.getStringExtra(Intent.EXTRA_TEXT);
        if (sharedText == null || sharedText.trim().isEmpty()) {
            CharSequence extraSubject = intent.getCharSequenceExtra(Intent.EXTRA_SUBJECT);
            if (extraSubject != null) sharedText = extraSubject.toString();
        }

        // Priority 1: Check for Image URI first! (Receipt screenshots from PhonePe, GPay, Gallery)
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

        final String captionText = sharedText;

        if (imageUri != null) {
            try {
                Toast.makeText(this, "⚡ Scanning receipt image...", Toast.LENGTH_SHORT).show();
                InputImage image = InputImage.fromFilePath(this, imageUri);
                TextRecognizer recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
                recognizer.process(image)
                    .addOnSuccessListener(visionText -> {
                        String ocrText = visionText.getText();
                        String combined = (ocrText != null ? ocrText : "") + "\n" + (captionText != null ? captionText : "");
                        if (!combined.trim().isEmpty()) {
                            processSharedTextAndPrefill(combined);
                        } else {
                            openFallbackQuickAdd();
                        }
                    })
                    .addOnFailureListener(e -> {
                        Log.e("FinoraOCR", "OCR processing failed: ", e);
                        if (captionText != null && !captionText.trim().isEmpty()) {
                            processSharedTextAndPrefill(captionText);
                        } else {
                            openFallbackQuickAdd();
                        }
                    });
                return;
            } catch (Exception e) {
                Log.e("FinoraOCR", "Failed to load InputImage from uri: " + imageUri, e);
                if (captionText != null && !captionText.trim().isEmpty()) {
                    processSharedTextAndPrefill(captionText);
                    return;
                }
                openFallbackQuickAdd();
                return;
            }
        }

        // Priority 2: Pure plain text without any image (e.g. copied SMS or text share)
        if (captionText != null && !captionText.trim().isEmpty()) {
            processSharedTextAndPrefill(captionText);
            return;
        }

        // Fallback
        openFallbackQuickAdd();
    }

    private void processSharedTextAndPrefill(String text) {
        ParsedReceipt receipt = parseSharedReceiptText(text);
        if (receipt.amount <= 0 && (receipt.payee == null || receipt.payee.isEmpty())) {
            openFallbackQuickAdd();
            return;
        }

        String toastMsg;
        if (!receipt.payee.isEmpty() && receipt.amount > 0) {
            toastMsg = "⚡ FINORA: " + receipt.payee + " (₹" + String.format(Locale.US, "%.2f", receipt.amount) + ")";
        } else if (receipt.amount > 0) {
            toastMsg = "⚡ FINORA: ₹" + String.format(Locale.US, "%.2f", receipt.amount);
        } else if (!receipt.payee.isEmpty()) {
            toastMsg = "⚡ FINORA: " + receipt.payee;
        } else {
            toastMsg = "⚡ FINORA: Transaction Opened";
        }
        Toast.makeText(this, toastMsg, Toast.LENGTH_LONG).show();

        final ParsedReceipt r = receipt;
        final String formattedAmount = r.amount > 0 ? String.format(Locale.US, "%.2f", r.amount) : "";
        final String safePayee = (r.payee != null) ? r.payee.replace("'", "\\'") : "";

        final String js = String.format(Locale.US,
            "(function() { " +
            "  function fill() { " +
            "    if (window.populateQuickAddModal) { " +
            "      window.populateQuickAddModal('expense', '%s', '%s', 'Shared via %s'); " +
            "      return true; " +
            "    } else if (window.openQuickAddModal) { " +
            "      window.openQuickAddModal('expense'); " +
            "      const t = document.querySelector('#quickAddModal input[name=\"title\"]'); " +
            "      const a = document.querySelector('#quickAddModal input[name=\"amount\"]'); " +
            "      const d = document.querySelector('#quickAddModal input[name=\"description\"]'); " +
            "      if (t && '%s' !== '') { t.value = '%s'; t.dispatchEvent(new Event('input', {bubbles:true})); } " +
            "      if (a && '%s' !== '') { a.value = '%s'; a.dispatchEvent(new Event('input', {bubbles:true})); } " +
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
            formattedAmount,
            safePayee,
            r.sourceApp,
            safePayee,
            safePayee,
            formattedAmount,
            formattedAmount,
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
