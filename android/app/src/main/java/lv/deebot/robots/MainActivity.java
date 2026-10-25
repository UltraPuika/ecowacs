package lv.deebot.robots;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.text.InputType;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.Toast;

/**
 * A thin full-screen wrapper around the web app running on the home server
 * (Raspberry Pi). All robot logic stays on the server; this app only stores
 * the server address and shows the page.
 */
public class MainActivity extends Activity {
    private static final String PREFS = "robots";
    private static final String KEY_URL = "server_url";

    private WebView web;
    private boolean errorDialogShown;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        setContentView(web);
        configureWebView();

        String url = savedUrl();
        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else if (url == null) {
            askForAddress();
        } else {
            web.loadUrl(url);
        }
    }

    private void configureWebView() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMediaPlaybackRequiresUserGesture(true);
        // Text size follows the phone's font-size setting (helpful for older users).

        CookieManager.getInstance().setAcceptCookie(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (isOwnServer(uri)) return false;
                // Links to other sites (e.g. documentation) open in the normal browser.
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (ActivityNotFoundException ignored) {
                    // nothing can open it
                }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showConnectionError();
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
            }
        });

        web.setDownloadListener((url, userAgent, contentDisposition, mimeType, length) -> {
            try {
                DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
                String cookie = CookieManager.getInstance().getCookie(url);
                if (cookie != null) req.addRequestHeader("Cookie", cookie);
                req.setMimeType(mimeType);
                String name = URLUtil.guessFileName(url, contentDisposition, mimeType);
                req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                dm.enqueue(req);
                Toast.makeText(this, R.string.downloading, Toast.LENGTH_SHORT).show();
            } catch (RuntimeException e) {
                Toast.makeText(this, R.string.download_failed, Toast.LENGTH_LONG).show();
            }
        });
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, MODE_PRIVATE);
    }

    private String savedUrl() {
        return prefs().getString(KEY_URL, null);
    }

    private boolean isOwnServer(Uri uri) {
        String saved = savedUrl();
        if (saved == null) return false;
        Uri server = Uri.parse(saved);
        return safeEquals(uri.getScheme(), server.getScheme())
                && safeEquals(uri.getHost(), server.getHost())
                && uri.getPort() == server.getPort();
    }

    private static boolean safeEquals(String a, String b) {
        return a == null ? b == null : a.equalsIgnoreCase(b);
    }

    /** Accepts "192.168.1.10:8080", "robots.lan" or a full http(s) URL. */
    static String normalize(String input) {
        String text = input == null ? "" : input.trim();
        if (text.isEmpty()) return null;
        if (!text.startsWith("http://") && !text.startsWith("https://")) text = "http://" + text;
        Uri uri = Uri.parse(text);
        if (uri.getHost() == null || uri.getHost().isEmpty()) return null;
        String port = uri.getPort() > 0 ? ":" + uri.getPort() : "";
        return uri.getScheme() + "://" + uri.getHost() + port + "/";
    }

    private void askForAddress() {
        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setHint(R.string.setup_hint);
        input.setTextSize(20);
        String current = savedUrl();
        if (current != null) input.setText(current);

        FrameLayout box = new FrameLayout(this);
        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        box.setPadding(pad, pad / 2, pad, 0);
        box.addView(input);

        AlertDialog.Builder builder = new AlertDialog.Builder(this)
                .setTitle(R.string.setup_title)
                .setMessage(R.string.setup_message)
                .setView(box)
                .setCancelable(current != null)
                .setPositiveButton(R.string.save, null);
        if (current != null) builder.setNegativeButton(R.string.cancel, null);

        AlertDialog dialog = builder.create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String url = normalize(input.getText().toString());
            if (url == null) {
                input.setError(getString(R.string.setup_invalid));
                return;
            }
            prefs().edit().putString(KEY_URL, url).apply();
            dialog.dismiss();
            errorDialogShown = false;
            web.clearHistory();
            web.loadUrl(url);
        }));
        dialog.show();
    }

    private void showConnectionError() {
        if (errorDialogShown || isFinishing()) return;
        errorDialogShown = true;
        String url = savedUrl();
        web.loadUrl("about:blank");
        new AlertDialog.Builder(this)
                .setTitle(R.string.error_title)
                .setMessage(getString(R.string.error_message, url))
                .setCancelable(false)
                .setPositiveButton(R.string.retry, (d, w) -> {
                    errorDialogShown = false;
                    if (url != null) web.loadUrl(url);
                })
                .setNegativeButton(R.string.change_address, (d, w) -> {
                    errorDialogShown = false;
                    askForAddress();
                })
                .show();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onDestroy() {
        web.destroy();
        super.onDestroy();
    }
}
