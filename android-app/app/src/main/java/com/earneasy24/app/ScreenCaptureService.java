package com.earneasy24.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.provider.Settings;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.nio.ByteBuffer;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ScreenCaptureService extends Service {
    static final String ACTION_START_CAPTURE = "com.earneasy24.app.START_CAPTURE";
    static final String ACTION_STOP = "com.earneasy24.app.STOP";
    static final String EXTRA_RESULT_CODE = "result_code";
    static final String EXTRA_RESULT_DATA = "result_data";

    private static final String CHANNEL_ID = "screen_capture";
    private static final int NOTIFICATION_ID = 4024;

    private final Handler mainHandler = new Handler();
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    private AppSettings settings;
    private AiVisionClient aiVisionClient;
    private WindowManager windowManager;
    private View panelView;
    private RegionSelectionView regionSelectionView;
    private WindowManager.LayoutParams panelParams;
    private TextView statusText;
    private TextView resultText;
    private Button copyButton;
    private String lastResult = "";

    private HandlerThread captureThread;
    private Handler captureHandler;
    private MediaProjection mediaProjection;
    private VirtualDisplay virtualDisplay;
    private ImageReader imageReader;
    private int captureWidth;
    private int captureHeight;
    private int captureDensity;

    @Override
    public void onCreate() {
        super.onCreate();
        settings = new AppSettings(this);
        aiVisionClient = new AiVisionClient();
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        createNotificationChannel();
        startForegroundCompat("Ready");
        showPanel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (intent != null && ACTION_START_CAPTURE.equals(intent.getAction())) {
            int resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, 0);
            Intent resultData = intent.getParcelableExtra(EXTRA_RESULT_DATA);
            startForegroundCompat("Capturing screen");
            startCapture(resultCode, resultData);
        }
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        removeRegionSelector();
        removePanel();
        stopCapture();
        executor.shutdownNow();
        super.onDestroy();
    }

    private void startCapture(int resultCode, Intent resultData) {
        if (resultData == null) {
            setStatus("Screen capture permission missing");
            return;
        }

        stopCapture();
        captureThread = new HandlerThread("EarnEasy24Capture");
        captureThread.start();
        captureHandler = new Handler(captureThread.getLooper());

        captureWidth = getResources().getDisplayMetrics().widthPixels;
        captureHeight = getResources().getDisplayMetrics().heightPixels;
        captureDensity = getResources().getDisplayMetrics().densityDpi;

        imageReader = ImageReader.newInstance(captureWidth, captureHeight, PixelFormat.RGBA_8888, 2);
        MediaProjectionManager projectionManager =
                (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        mediaProjection = projectionManager.getMediaProjection(resultCode, resultData);
        mediaProjection.registerCallback(new MediaProjection.Callback() {
            @Override
            public void onStop() {
                mainHandler.post(() -> {
                    setStatus("Screen capture stopped");
                    releaseCaptureResources(false);
                });
            }
        }, captureHandler);

        virtualDisplay = mediaProjection.createVirtualDisplay(
                "EarnEasy24Capture",
                captureWidth,
                captureHeight,
                captureDensity,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                imageReader.getSurface(),
                null,
                captureHandler
        );
        setStatus("Screen capture active. Select Region, then Capture.");
    }

    private void stopCapture() {
        releaseCaptureResources(true);
    }

    private void releaseCaptureResources(boolean stopProjection) {
        if (virtualDisplay != null) {
            virtualDisplay.release();
            virtualDisplay = null;
        }
        if (imageReader != null) {
            imageReader.close();
            imageReader = null;
        }
        if (mediaProjection != null) {
            MediaProjection projection = mediaProjection;
            mediaProjection = null;
            if (stopProjection) {
                projection.stop();
            }
        }
        if (captureThread != null) {
            captureThread.quitSafely();
            captureThread = null;
            captureHandler = null;
        }
    }

    private void showPanel() {
        if (!Settings.canDrawOverlays(this) || panelView != null) {
            return;
        }

        panelView = buildPanel();
        panelParams = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                overlayType(),
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT
        );
        panelParams.gravity = Gravity.TOP | Gravity.START;
        panelParams.x = dp(14);
        panelParams.y = dp(70);
        windowManager.addView(panelView, panelParams);
    }

    private View buildPanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(10), dp(8), dp(10), dp(10));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(34, 34, 34));
        background.setStroke(dp(1), Color.rgb(78, 78, 78));
        background.setCornerRadius(dp(8));
        panel.setBackground(background);

        TextView title = new DragHandleTextView(this);
        title.setText(R.string.overlay_title);
        title.setTextSize(14);
        title.setTextColor(Color.WHITE);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 0, 0, dp(6));
        title.setOnTouchListener(new DragTouchListener());
        panel.addView(title, new LinearLayout.LayoutParams(dp(248), LinearLayout.LayoutParams.WRAP_CONTENT));

        statusText = text("Ready", 12, Color.rgb(210, 210, 210));
        panel.addView(statusText, new LinearLayout.LayoutParams(dp(248), LinearLayout.LayoutParams.WRAP_CONTENT));

        resultText = text("Result: -", 16, Color.rgb(46, 204, 113));
        resultText.setPadding(0, dp(6), 0, dp(6));
        panel.addView(resultText, new LinearLayout.LayoutParams(dp(248), LinearLayout.LayoutParams.WRAP_CONTENT));

        LinearLayout firstRow = row();
        firstRow.addView(panelButton("Start", v -> startActivity(new Intent(this, ProjectionPermissionActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))));
        firstRow.addView(panelButton("Stop", v -> stopSelf()));
        firstRow.addView(panelButton("Region", v -> showRegionSelector()));
        panel.addView(firstRow);

        LinearLayout secondRow = row();
        secondRow.addView(panelButton("Capture", v -> captureSelectedRegion()));
        copyButton = panelButton("Copy", v -> copyLastResult());
        copyButton.setEnabled(false);
        secondRow.addView(copyButton);
        secondRow.addView(panelButton("Settings", v -> startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))));
        panel.addView(secondRow);

        return panel;
    }

    private void showRegionSelector() {
        if (!Settings.canDrawOverlays(this)) {
            setStatus("Overlay permission is not enabled");
            return;
        }
        removeRegionSelector();
        regionSelectionView = new RegionSelectionView(this, region -> {
            settings.saveRegion(region);
            removeRegionSelector();
            setStatus("Region saved: " + settings.regionLabel());
        });
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                overlayType(),
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT
        );
        params.gravity = Gravity.TOP | Gravity.START;
        windowManager.addView(regionSelectionView, params);
        setStatus("Drag around the CAPTCHA region");
    }

    private void removeRegionSelector() {
        if (regionSelectionView != null) {
            try {
                windowManager.removeView(regionSelectionView);
            } catch (IllegalArgumentException ignored) {
            }
            regionSelectionView = null;
        }
    }

    private void captureSelectedRegion() {
        Rect region = settings.region();
        if (region.isEmpty()) {
            setStatus("Select Region first");
            return;
        }
        if (imageReader == null) {
            setStatus("Tap Start and approve screen capture first");
            return;
        }
        setStatus("Capturing selected region...");
        if (panelView != null) {
            panelView.setVisibility(View.INVISIBLE);
        }
        mainHandler.postDelayed(() -> {
            Bitmap cropped = null;
            try {
                cropped = captureBitmap(region);
            } catch (Exception exc) {
                setStatus("Capture failed: " + exc.getMessage());
            } finally {
                if (panelView != null) {
                    panelView.setVisibility(View.VISIBLE);
                }
            }
            if (cropped != null) {
                sendToAi(cropped);
            }
        }, 350);
    }

    private Bitmap captureBitmap(Rect requestedRegion) throws Exception {
        Image image = imageReader.acquireLatestImage();
        if (image == null) {
            throw new IllegalStateException("No screen frame available yet");
        }
        try {
            Image.Plane plane = image.getPlanes()[0];
            ByteBuffer buffer = plane.getBuffer();
            int pixelStride = plane.getPixelStride();
            int rowStride = plane.getRowStride();
            int rowPadding = rowStride - pixelStride * captureWidth;
            Bitmap padded = Bitmap.createBitmap(
                    captureWidth + rowPadding / pixelStride,
                    captureHeight,
                    Bitmap.Config.ARGB_8888
            );
            padded.copyPixelsFromBuffer(buffer);
            Bitmap screen = Bitmap.createBitmap(padded, 0, 0, captureWidth, captureHeight);
            padded.recycle();

            Rect region = new Rect(requestedRegion);
            if (!region.intersect(0, 0, screen.getWidth(), screen.getHeight())
                    || region.width() < 2
                    || region.height() < 2) {
                screen.recycle();
                throw new IllegalStateException("Selected region is outside the screen");
            }
            Bitmap crop = Bitmap.createBitmap(screen, region.left, region.top, region.width(), region.height());
            screen.recycle();
            return crop;
        } finally {
            image.close();
        }
    }

    private void sendToAi(Bitmap crop) {
        setStatus("Reading with AI...");
        executor.execute(() -> {
            try {
                String result = aiVisionClient.readCaptcha(crop, settings);
                boolean valid = CaptchaTextCleaner.isLengthValid(result, settings);
                mainHandler.post(() -> {
                    lastResult = result;
                    resultText.setText(result.isEmpty() ? "Result: -" : "Result: " + result);
                    copyButton.setEnabled(!result.isEmpty());
                    if (result.isEmpty()) {
                        setStatus("No readable text found");
                    } else if (!valid) {
                        setStatus("Result length outside configured range");
                    } else {
                        setStatus("Ready to copy. Review before paste.");
                    }
                });
            } catch (Exception exc) {
                mainHandler.post(() -> setStatus("AI failed: " + exc.getMessage()));
            } finally {
                crop.recycle();
            }
        });
    }

    private void copyLastResult() {
        if (lastResult.isEmpty()) {
            return;
        }
        ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText("Earn Easy24 CAPTCHA", lastResult));
        Toast.makeText(this, "Copied cleaned answer", Toast.LENGTH_SHORT).show();
        setStatus("Copied. Paste manually in the target app.");
    }

    private void removePanel() {
        if (panelView != null) {
            try {
                windowManager.removeView(panelView);
            } catch (IllegalArgumentException ignored) {
            }
            panelView = null;
        }
    }

    private void setStatus(String status) {
        if (statusText != null) {
            statusText.setText(status);
        }
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.notify(NOTIFICATION_ID, notification(status));
    }

    private void startForegroundCompat(String status) {
        Notification notification = notification(status);
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private Notification notification(String status) {
        Intent openIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                0,
                openIntent,
                PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return builder
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setContentTitle("Earn Easy24 Assistant")
                .setContentText(status)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .build();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Screen capture",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Earn Easy24 screen capture service");
            NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            manager.createNotificationChannel(channel);
        }
    }

    private int overlayType() {
        return Build.VERSION.SDK_INT >= 26
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;
    }

    private Button panelButton(String label, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(11);
        button.setPadding(dp(4), 0, dp(4), 0);
        button.setOnClickListener(listener);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(40), 1f);
        params.setMargins(dp(2), dp(2), dp(2), dp(2));
        button.setLayoutParams(params);
        return button;
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        return row;
    }

    private TextView text(String value, int sp, int color) {
        TextView text = new TextView(this);
        text.setText(value);
        text.setTextSize(sp);
        text.setTextColor(color);
        return text;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static final class DragHandleTextView extends TextView {
        DragHandleTextView(Context context) {
            super(context);
        }

        @Override
        public boolean performClick() {
            super.performClick();
            return true;
        }
    }

    private final class DragTouchListener implements View.OnTouchListener {
        private int initialX;
        private int initialY;
        private float initialTouchX;
        private float initialTouchY;
        private boolean moved;

        @Override
        public boolean onTouch(View view, MotionEvent event) {
            switch (event.getAction()) {
                case MotionEvent.ACTION_DOWN:
                    initialX = panelParams.x;
                    initialY = panelParams.y;
                    initialTouchX = event.getRawX();
                    initialTouchY = event.getRawY();
                    moved = false;
                    return true;
                case MotionEvent.ACTION_MOVE:
                    if (Math.abs(event.getRawX() - initialTouchX) > dp(2)
                            || Math.abs(event.getRawY() - initialTouchY) > dp(2)) {
                        moved = true;
                    }
                    panelParams.x = initialX + Math.round(event.getRawX() - initialTouchX);
                    panelParams.y = initialY + Math.round(event.getRawY() - initialTouchY);
                    windowManager.updateViewLayout(panelView, panelParams);
                    return true;
                case MotionEvent.ACTION_UP:
                    if (!moved) {
                        view.performClick();
                    }
                    return true;
                case MotionEvent.ACTION_CANCEL:
                    return true;
                default:
                    return false;
            }
        }
    }

    private final class RegionSelectionView extends View {
        private final Paint shadePaint = new Paint();
        private final Paint borderPaint = new Paint();
        private final Paint textPaint = new Paint();
        private final RegionCallback callback;
        private final Rect selection = new Rect();
        private int startX;
        private int startY;

        RegionSelectionView(Context context, RegionCallback callback) {
            super(context);
            this.callback = callback;
            setBackgroundColor(Color.TRANSPARENT);
            shadePaint.setColor(Color.argb(145, 0, 0, 0));
            borderPaint.setColor(Color.rgb(46, 204, 113));
            borderPaint.setStyle(Paint.Style.STROKE);
            borderPaint.setStrokeWidth(dp(2));
            textPaint.setColor(Color.WHITE);
            textPaint.setTextSize(dp(16));
            textPaint.setAntiAlias(true);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            canvas.drawRect(0, 0, getWidth(), getHeight(), shadePaint);
            canvas.drawText("Drag around the CAPTCHA region", dp(20), dp(44), textPaint);
            if (!selection.isEmpty()) {
                canvas.drawRect(selection, borderPaint);
            }
        }

        @Override
        public boolean onTouchEvent(MotionEvent event) {
            int x = Math.round(event.getX());
            int y = Math.round(event.getY());
            switch (event.getAction()) {
                case MotionEvent.ACTION_DOWN:
                    startX = x;
                    startY = y;
                    selection.set(x, y, x, y);
                    invalidate();
                    return true;
                case MotionEvent.ACTION_MOVE:
                    selection.set(Math.min(startX, x), Math.min(startY, y), Math.max(startX, x), Math.max(startY, y));
                    invalidate();
                    return true;
                case MotionEvent.ACTION_UP:
                    selection.set(Math.min(startX, x), Math.min(startY, y), Math.max(startX, x), Math.max(startY, y));
                    if (selection.width() >= dp(8) && selection.height() >= dp(8)) {
                        callback.onRegionSelected(new Rect(selection));
                    } else {
                        performClick();
                        removeRegionSelector();
                        setStatus("Region selection cancelled");
                    }
                    return true;
                default:
                    return false;
            }
        }

        @Override
        public boolean performClick() {
            super.performClick();
            return true;
        }
    }

    private interface RegionCallback {
        void onRegionSelected(Rect region);
    }
}
