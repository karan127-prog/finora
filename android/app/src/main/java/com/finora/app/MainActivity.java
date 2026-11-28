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
        if (t.matches("(?i)^(₹|rs\\.?|inr|completed|successful|success|payment|transaction|date|upi|utr|ref|details|debited|deducted|deduction|credited|banking|account|balance|avail|total|bill|order|paid|sent|transfer|money|\\d).*")) return false;
        if (t.matches("^[\\d,.:\\-\\s/]+$")) return false;
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

        // 2. Determine Income vs Expense (Accurate Direction Detection)
        // Check for incoming money (Income) markers:
        boolean hasIncomeSignals = Pattern.compile("(?i)\\b(paid\\s+you|sent\\s+you|received\\s+from|money\\s+received|payment\\s+received\\s+from|received\\s+(?:rs\\.?|inr|₹)?\\s*[\\d,.]+|credited\\s+to|credited\\s+with|credited\\s+by|has\\s+been\\s+credited|a/c\\s+credited|account\\s+credited|cashback|refund|added\\s+to\\s+(?:your\\s+)?(?:account|wallet))\\b").matcher(raw).find();

        // Check for outgoing money (Expense) markers:
        boolean hasExpenseSignals = Pattern.compile("(?i)\\b(paid\\s+to|payment\\s+to|transfer\\s+to|transferred\\s+to|sent\\s+to|money\\s+sent\\s+to|debited\\s+from|amount\\s+debited|account\\s+debited|a/c\\s+debited|debited\\s+by|debited\\s+for|deducted\\s+from|amount\\s+deducted|a/c\\s+deducted|deducted\\s+by|deducted\\s+for|bill\\s+payment|recharge\\s+for|purchase\\s+of|spent\\s+on)\\b").matcher(raw).find();

        boolean isIncome = false;
        // Priority 1: Clear outgoing debited/deducted markers always mean Expense
        if (Pattern.compile("(?i)\\b(debited\\s+from|deducted\\s+from|a/c\\s+debited|account\\s+debited|amount\\s+debited|amount\\s+deducted|paid\\s+to|payment\\s+to)\\b").matcher(raw).find()) {
            isIncome = false;
        }
        // Priority 2: Clear incoming credited/received markers mean Income
        else if (Pattern.compile("(?i)\\b(credited\\s+to|a/c\\s+credited|account\\s+credited|paid\\s+you|sent\\s+you|received\\s+from|payment\\s+received\\s+from)\\b").matcher(raw).find()) {
            isIncome = true;
        }
        // Priority 3: General signals
        else if (hasIncomeSignals && !hasExpenseSignals) {
            isIncome = true;
        } else if (!hasIncomeSignals && hasExpenseSignals) {
            isIncome = false;
        } else if (hasIncomeSignals && hasExpenseSignals) {
            isIncome = Pattern.compile("(?i)\\b(credited|received)\\b").matcher(raw).find();
        } else {
            isIncome = Pattern.compile("(?i)\\b(received|credited)\\b").matcher(raw).find();
        }
        res.type = isIncome ? "income" : "expense";

        String[] lines = raw.split("\\r?\\n");

        // 3. Extract Amount (Robust Multi-Stage Deducted & UPI Parser)
        // Pattern 1: Explicit Debit / Deducted Keywords with amount
        Pattern pDebit = Pattern.compile("(?:debited\\s+(?:by|for|with|of)?|deducted\\s+(?:by|for|with|of|from\\s+account\\s+for)?|amount\\s+(?:debited|deducted|paid)\\s*(?:is|of)?:?|amt\\s+(?:debited|deducted):?)[\\s\\n:]*(?:rs\\.?|inr|₹)?[\\s\\n]*([0-9,]+(?:\\.[0-9]{1,2})?)", Pattern.CASE_INSENSITIVE);
        Matcher mDebit = pDebit.matcher(raw);
        if (mDebit.find()) {
            try {
                res.amount = Double.parseDouble(mDebit.group(1).replace(",", ""));
            } catch (Exception ignored) {}
        }

        // Pattern 2: Suffix Debit / Deduction (e.g. "450.00 deducted", "₹450 debited")
        if (res.amount <= 0) {
            Pattern pSuffix = Pattern.compile("(?:rs\\.?|inr|₹)?[\\s\\n]*([0-9,]+(?:\\.[0-9]{1,2})?)[\\s\\n]*(?:debited|deducted|spent|paid)", Pattern.CASE_INSENSITIVE);
            Matcher mSuffix = pSuffix.matcher(raw);
            if (mSuffix.find()) {
                try {
                    res.amount = Double.parseDouble(mSuffix.group(1).replace(",", ""));
                } catch (Exception ignored) {}
            }
        }

        // Pattern 3: Currency Symbol followed by amount (excluding remaining balance lines)
        if (res.amount <= 0) {
            for (String l : lines) {
                String lc = l.trim();
                if (lc.matches("(?i).*\\b(bal|balance|avail|avl|acct|a/c)\\b.*") && !lc.matches("(?i).*\\b(debited|deducted|paid|credited)\\b.*")) {
                    continue;
                }
                Matcher mCurr = Pattern.compile("(?:rs\\.?|inr|₹)[\\s\\n]*([0-9,]+(?:\\.[0-9]{1,2})?)", Pattern.CASE_INSENSITIVE).matcher(lc);
                if (mCurr.find()) {
                    try {
                        double parsed = Double.parseDouble(mCurr.group(1).replace(",", ""));
                        if (parsed > 0 && parsed < 10000000) {
                            res.amount = parsed;
                            break;
                        }
                    } catch (Exception ignored) {}
                }
            }
        }

        // Pattern 4: Amount followed by currency symbol (500 ₹, 450.00 Rs)
        if (res.amount <= 0) {
            Pattern pCurrTrail = Pattern.compile("([0-9,]+(?:\\.[0-9]{1,2})?)[\\s\\n]*(?:rs\\.?|inr|₹)", Pattern.CASE_INSENSITIVE);
            Matcher mCurrTrail = pCurrTrail.matcher(raw);
            if (mCurrTrail.find()) {
                try {
                    res.amount = Double.parseDouble(mCurrTrail.group(1).replace(",", ""));
                } catch (Exception ignored) {}
            }
        }

        // Pattern 5: Keywords 'payment of', 'paid', 'sent', 'transfer of'
        if (res.amount <= 0) {
            Pattern pPaid = Pattern.compile("(?:payment\\s+(?:of)?|paid|sent|transfer\\s+(?:of)?|amount:?)[\\s\\n:]*(?:rs\\.?|inr|₹)?[\\s\\n]*([0-9,]+(?:\\.[0-9]{1,2})?)", Pattern.CASE_INSENSITIVE);
            Matcher mPaid = pPaid.matcher(raw);
            if (mPaid.find()) {
                try {
                    res.amount = Double.parseDouble(mPaid.group(1).replace(",", ""));
                } catch (Exception ignored) {}
            }
        }

        // Pattern 6: Line with standalone number
        if (res.amount <= 0) {
            for (String l : lines) {
                String clean = l.trim().replaceAll("(?i)^[₹RsINR\\s:]+", "").replaceAll("(?i)[₹RsINR\\s]+$", "");
                if (clean.matches("^[0-9,]+(\\.[0-9]{1,2})?$")) {
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

        // Strategy 1: Incoming - 'Name paid you' or 'Name sent you'
        Matcher mPaidYou = Pattern.compile("(?i)([A-Za-z0-9&'.-][A-Za-z0-9\\s&'.-]{1,30}?)\\s+(?:paid\\s+you|sent\\s+you)").matcher(raw);
        if (mPaidYou.find()) {
            String cand = mPaidYou.group(1).trim();
            if (isValidPayeeCandidate(cand)) {
                detectedName = cand;
            }
        }

        // Strategy 2: Incoming - 'from Name' or 'received from Name'
        if (detectedName.isEmpty() && isIncome) {
            Matcher mFrom = Pattern.compile("(?i)\\bfrom:?\\s+([A-Za-z0-9&'.-][A-Za-z0-9\\s&'.-]{1,30}?)(?:\\r?\\n|\\s*[\\(\\[;]|\\s+\\b(?:on|via|ref|completed|successful|using|debited|deducted|credited)\\b|$)").matcher(raw);
            if (mFrom.find()) {
                String cand = mFrom.group(1).trim();
                if (isValidPayeeCandidate(cand)) {
                    detectedName = cand;
                }
            }
        }

        // Strategy 3: Outgoing - 'Payment of X to Name' or 'Paid X to Name'
        if (detectedName.isEmpty()) {
            Matcher mToAfterAmt = Pattern.compile("(?i)(?:payment\\s+(?:of\\s+)?|paid\\s+|sent\\s+)(?:rs\\.?|inr|₹)?\\s*[\\d,.]+\\s+to\\s+([A-Za-z0-9&'.-][A-Za-z0-9\\s&'.-]{1,34}?)(?:\\r?\\n|\\s*[\\(\\[;]|\\b(?:on|via|ref|completed|successful|using|debited|deducted)\\b|$)").matcher(raw);
            if (mToAfterAmt.find()) {
                String cand = mToAfterAmt.group(1).trim();
                if (isValidPayeeCandidate(cand)) {
                    detectedName = cand;
                }
            }
        }

        // Strategy 4: Standalone Header line: "Paid to", "Paid", "To:", "Payment to", "Transfer to", "Money sent to", "Money sent", "Received from"
        if (detectedName.isEmpty()) {
            for (int i = 0; i < lines.length; i++) {
                String line = lines[i].trim();
                if (line.matches("(?i)^(paid\\s+to|paid|payment\\s+to|transfer\\s+to|transferred\\s+to|sent\\s+to|money\\s+sent\\s+(?:to)?|money\\s+sent|received\\s+from|to:?|from:?)$")) {
                    if (i + 1 < lines.length) {
                        String nextLine = lines[i + 1].trim();
                        if (isValidPayeeCandidate(nextLine)) {
                            detectedName = nextLine;
                            break;
                        }
                    }
                }
            }
        }

        // Strategy C: Inline Header: "Paid to Ram Kumar" or "To: Vijay Store"
        if (detectedName.isEmpty()) {
            for (String line : lines) {
                Matcher mInline = Pattern.compile("(?i)^(?:paid\\s+to|payment\\s+to|transfer\\s+to|transferred\\s+to|sent\\s+to|money\\s+sent\\s+(?:to)?|received\\s+from|to:|from:)\\s+([A-Za-z0-9\\s&'.-]{2,35})").matcher(line);
                if (mInline.find()) {
                    String cand = mInline.group(1).trim();
                    if (isValidPayeeCandidate(cand)) {
                        detectedName = cand;
                        break;
                    }
                }
            }
        }

        // Strategy D: Bank SMS pattern: towards UPI/Merchant/ref or by UPI: Merchant
        if (detectedName.isEmpty()) {
            Matcher mSms = Pattern.compile("(?i)(?:towards\\s+upi/|by\\s+upi:\\s*|to\\s+vpa\\s+|towards\\s+)([A-Za-z0-9\\s&'.-]{2,30})").matcher(raw);
            if (mSms.find()) {
                String cand = mSms.group(1).split("/")[0].trim();
                if (isValidPayeeCandidate(cand)) {
                    detectedName = cand;
                }
            }
        }

        // Strategy E: Banking / Merchant label: "Banking Name: XYZ"
        if (detectedName.isEmpty()) {
            for (String line : lines) {
                Matcher mBank = Pattern.compile("(?i)(?:banking\\s+name:?|merchant:?)\\s*([A-Za-z0-9\\s&'.-]{2,35})").matcher(line);
                if (mBank.find()) {
                    String cand = mBank.group(1).trim();
                    if (isValidPayeeCandidate(cand)) {
                        detectedName = cand;
                        break;
                    }
                }
            }
        }

        // Fallback F: Extract name from UPI handle (e.g. "rohit.sharma@oksbi" -> "Rohit Sharma")
        if (detectedName.isEmpty()) {
            Pattern pUpi = Pattern.compile("(?i)([a-zA-Z0-9.-]{3,25})@(okhdfcbank|okaxis|oksbi|okicici|ybl|ibl|paytm|axl|upi)");
            Matcher mUpi = pUpi.matcher(raw);
            if (mUpi.find()) {
                String u = mUpi.group(1).replace(".", " ").replace("-", " ").trim();
                if (u.length() >= 3 && isValidPayeeCandidate(u)) {
                    detectedName = u;
                }
            }
        }

        // Fallback G: First meaningful valid line that is not an app name or status
        if (detectedName.isEmpty()) {
            for (String l : lines) {
                String cl = l.trim();
                if (isValidPayeeCandidate(cl) && !cl.matches("(?i).*(google\\s*pay|phonepe|paytm|bhim|cred|bank|state\\s+bank|hdfc|icici|axis|pnb|kotak|success|transaction|completed|debited|deducted|credited|ref|utr).*")) {
                    detectedName = cl;
                    break;
                }
            }
        }

        if (detectedName.isEmpty()) {
            detectedName = isIncome ? "UPI Sender" : "UPI Merchant";
        }

        // Clean up unwanted trailing tags and balance strings
        detectedName = detectedName.replaceAll("(?i)\\b(bal|balance|avl|avail|using|on|via|account|phonepe|gpay|paytm|completed|successful|debited|deducted)\\b.*", "").trim();
        detectedName = detectedName.replaceAll("^[\\s.,:-]+|[\\s.,:-]+$", "");

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
