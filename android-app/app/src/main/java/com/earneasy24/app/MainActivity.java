package com.earneasy24.app;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.util.Locale;

public final class MainActivity extends android.app.Activity {
    private AppSettings settings;
    private EditText apiUrlInput;
    private EditText modelInput;
    private EditText apiKeyInput;
    private EditText minLengthInput;
    private EditText maxLengthInput;
    private EditText loopDelayInput;
    private EditText cooldownInput;
    private TextView permissionStatus;
    private TextView regionStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        settings = new AppSettings(this);
        setContentView(buildContent());
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatus();
    }

    private View buildContent() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        scrollView.setBackgroundColor(Color.rgb(24, 24, 24));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(18), dp(20), dp(24));
        scrollView.addView(root);

        TextView title = label("Earn Easy24 Android Assistant", 22, Color.WHITE);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title, matchWrap());

        TextView subtitle = label("Floating screen OCR panel for user-reviewed answers.", 14, Color.rgb(190, 190, 190));
        subtitle.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(subtitle, matchWrap());

        permissionStatus = label("", 14, Color.rgb(230, 230, 230));
        permissionStatus.setPadding(0, dp(18), 0, dp(6));
        root.addView(permissionStatus, matchWrap());

        regionStatus = label("", 14, Color.rgb(230, 230, 230));
        regionStatus.setPadding(0, 0, 0, dp(12));
        root.addView(regionStatus, matchWrap());

        LinearLayout actionRow = row();
        Button overlayPermission = button("Overlay Permission");
        overlayPermission.setOnClickListener(v -> openOverlaySettings());
        actionRow.addView(overlayPermission, rowButtonParams());

        Button start = button("Start Panel");
        start.setOnClickListener(v -> startPanel());
        actionRow.addView(start, rowButtonParams());
        root.addView(actionRow, matchWrap());

        LinearLayout secondRow = row();
        Button stop = button("Stop");
        stop.setOnClickListener(v -> stopService(new Intent(this, ScreenCaptureService.class)));
        secondRow.addView(stop, rowButtonParams());

        Button requestNotifications = button("Notification Permission");
        requestNotifications.setOnClickListener(v -> requestNotificationPermission());
        secondRow.addView(requestNotifications, rowButtonParams());
        root.addView(secondRow, matchWrap());

        addSection(root, "AI Settings");
        apiUrlInput = input(settings.apiUrl(), false, false);
        root.addView(field("API URL", apiUrlInput));
        modelInput = input(settings.model(), false, false);
        root.addView(field("Vision Model", modelInput));
        apiKeyInput = input(settings.apiKey(), false, true);
        root.addView(field("API Key", apiKeyInput));

        addSection(root, "Tuning");
        minLengthInput = input(String.valueOf(settings.minLength()), true, false);
        root.addView(field("Min CAPTCHA Length", minLengthInput));
        maxLengthInput = input(String.valueOf(settings.maxLength()), true, false);
        root.addView(field("Max CAPTCHA Length", maxLengthInput));
        loopDelayInput = input(String.valueOf(settings.loopDelaySeconds()), false, false);
        root.addView(field("Loop Delay Seconds", loopDelayInput));
        cooldownInput = input(String.valueOf(settings.cooldownSeconds()), false, false);
        root.addView(field("Cooldown Seconds", cooldownInput));

        Button save = button("Save Settings");
        save.setOnClickListener(v -> saveSettings());
        root.addView(save, matchWrap());

        TextView note = label(
                "This version captures only the selected screen region and shows the cleaned result for review/copy. It does not use Accessibility APIs or auto-click other apps.",
                13,
                Color.rgb(180, 180, 180)
        );
        note.setPadding(0, dp(18), 0, 0);
        root.addView(note, matchWrap());

        refreshStatus();
        return scrollView;
    }

    private void startPanel() {
        saveSettings();
        requestNotificationPermission();
        if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Enable Display over other apps first.", Toast.LENGTH_LONG).show();
            openOverlaySettings();
            return;
        }
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestNotificationPermission();
            Toast.makeText(this, "Approve notifications, then tap Start Panel again.", Toast.LENGTH_LONG).show();
            return;
        }
        startActivity(new Intent(this, ProjectionPermissionActivity.class));
    }

    private void saveSettings() {
        settings.saveNetwork(
                apiUrlInput.getText().toString(),
                modelInput.getText().toString(),
                apiKeyInput.getText().toString()
        );
        settings.saveTuning(
                parseInt(minLengthInput, settings.minLength()),
                parseInt(maxLengthInput, settings.maxLength()),
                parseFloat(loopDelayInput, settings.loopDelaySeconds()),
                parseFloat(cooldownInput, settings.cooldownSeconds())
        );
        Toast.makeText(this, "Settings saved", Toast.LENGTH_SHORT).show();
        refreshStatus();
    }

    private void openOverlaySettings() {
        Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION);
        intent.setData(Uri.parse("package:" + getPackageName()));
        startActivity(intent);
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 100);
        }
    }

    private void refreshStatus() {
        if (permissionStatus != null) {
            permissionStatus.setText(String.format(
                    Locale.US,
                    "Overlay permission: %s",
                    Settings.canDrawOverlays(this) ? "Enabled" : "Not enabled"
            ));
        }
        if (regionStatus != null) {
            regionStatus.setText(String.format(Locale.US, "Capture region: %s", settings.regionLabel()));
        }
    }

    private static int parseInt(EditText input, int fallback) {
        try {
            return Integer.parseInt(input.getText().toString().trim());
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static float parseFloat(EditText input, float fallback) {
        try {
            return Float.parseFloat(input.getText().toString().trim());
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private LinearLayout field(String label, EditText input) {
        LinearLayout wrapper = new LinearLayout(this);
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setPadding(0, dp(6), 0, dp(10));
        wrapper.addView(label(label, 13, Color.rgb(210, 210, 210)), matchWrap());
        wrapper.addView(input, matchWrap());
        return wrapper;
    }

    private EditText input(String value, boolean number, boolean password) {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(value);
        input.setTextColor(Color.WHITE);
        input.setHintTextColor(Color.rgb(140, 140, 140));
        input.setBackgroundColor(Color.rgb(55, 55, 55));
        input.setPadding(dp(10), dp(8), dp(10), dp(8));
        if (password) {
            input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        } else if (number) {
            input.setInputType(InputType.TYPE_CLASS_NUMBER);
        } else {
            input.setInputType(InputType.TYPE_CLASS_TEXT);
        }
        return input;
    }

    private void addSection(LinearLayout root, String text) {
        TextView section = label(text, 15, Color.rgb(46, 204, 113));
        section.setPadding(0, dp(18), 0, dp(4));
        root.addView(section, matchWrap());
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        row.setPadding(0, dp(4), 0, dp(4));
        return row;
    }

    private Button button(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        return button;
    }

    private TextView label(String text, int sp, int color) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(sp);
        label.setTextColor(color);
        return label;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams rowButtonParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        params.setMargins(dp(4), 0, dp(4), 0);
        return params;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
