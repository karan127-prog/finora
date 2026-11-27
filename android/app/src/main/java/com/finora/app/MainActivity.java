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
import android.widget.Toast;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    public static final String DEFAULT_URL = "http://192.168.1.2:5000";
    private static final String PREFS_NAME = "FinoraPrefs";
    private static final String KEY_SERVER_URL = "server_url";

    private WebView webView;
    private SwipeRefreshLayout swipeRefresh;
    private SharedPreferences prefs;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);

        android.widget.RelativeLayout layout = new android.widget.RelativeLayout(this);

        swipeRefresh = new SwipeRefreshLayout(this);
        webView = new WebView(this);

        // Native app look: Match app background and eliminate browser edge bounce
        webView.setBackgroundColor(0xFFF3F7FA);
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

        // Enable persistent cookies and third-party cookies across app restarts
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
        swipeRefresh.setColorSchemeColors(0xFF789BB8, 0xFFA9C5DC);

        String currentUrl = prefs.getString(KEY_SERVER_URL, DEFAULT_URL);
        webView.loadUrl(currentUrl);

        // Check and prompt for Notification Listener & Post Notification access
        checkNotificationPermissions();
        checkSmsPermissions();
        handleQuickAddIntent(getIntent());

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
        handleQuickAddIntent(intent);
    }

    private void handleQuickAddIntent(Intent intent) {
        if (intent == null || !intent.hasExtra("quick_amount")) return;

        double amount = intent.getDoubleExtra("quick_amount", 0);
        String payee = intent.getStringExtra("quick_payee");

        webView.postDelayed(() -> {
            String js = String.format(
                "if (window.openQuickAddModal) { " +
                "  window.openQuickAddModal('expense'); " +
                "  const t = document.querySelector('input[name=\"title\"]'); " +
                "  const a = document.querySelector('input[name=\"amount\"]'); " +
                "  if (t) t.value = '%s'; " +
                "  if (a) a.value = '%.2f'; " +
                "}",
                (payee != null ? payee.replace("'", "\\'") : "UPI Payment"),
                amount
            );
            webView.evaluateJavascript(js, null);
        }, 1200);
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
