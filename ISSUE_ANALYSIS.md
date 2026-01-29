# Image Generation HTTP 403 Error - Root Cause Analysis

## Issue Summary
Image generation fails with error: "Flow API request failed: HTTP Error 403"
Chinese error message: "生成失败: Flow API request failed: HTTP Error 403"

## Root Cause

### Primary Issue: reCAPTCHA Token Failure

The HTTP 403 error is caused by **failed reCAPTCHA validation**. The API response clearly states:

```json
{
  "error": {
    "code": 403,
    "message": "reCAPTCHA evaluation failed",
    "status": "PERMISSION_DENIED",
    "details": [
      {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "PUBLIC_ERROR_SOMETHING_WENT_WRONG"
      }
    ]
  }
}
```

### Request Analysis

From logs.txt, the request shows an **empty reCAPTCHA token**:

```json
{
  "clientContext": {
    "recaptchaToken": "",  // ← EMPTY!
    "sessionId": ";1769409971480"
  },
  "requests": [
    {
      "clientContext": {
        "recaptchaToken": "",  // ← EMPTY!
        "projectId": "d2e31057-1d62-4a69-ae53-82c9ab1419f0",
        "sessionId": ";1769409971480",
        "tool": "PINHOLE"
      },
      // ... rest of request
    }
  ]
}
```

### Underlying Cause: Browser Captcha Service Failure

The captcha method is set to `"browser"` in config/setting.toml, but the browser service is failing to start:

```
[BrowserCaptcha] ❌ 浏览器启动失败
[reCAPTCHA Browser] error
```

The error in the test output shows:
```
NotImplementedError at asyncio.base_events.py:503 in _make_subprocess_transport
```

This indicates that the Playwright browser automation is failing to launch on Windows with the current event loop policy.

## Secondary Issues

### Token Problems

Both tokens have high error counts:
- Token #1 (ID: 3): 16 consecutive errors, **disabled**, AT expired
- Token #2 (ID: 2): 24 consecutive errors, enabled, AT valid

## Solutions

### Solution 1: Switch to API-based Captcha Service (Recommended)

Change the captcha method from `browser` to an API service:

1. **Edit config/setting.toml**:
   ```toml
   [captcha]
   captcha_method = "yescaptcha"  # or "capmonster", "ezcaptcha", "capsolver"
   yescaptcha_api_key = "YOUR_API_KEY_HERE"
   yescaptcha_base_url = "https://api.yescaptcha.com"
   ```

2. **Get an API key** from one of these services:
   - YesCaptcha: https://yescaptcha.com/
   - CapMonster: https://capmonster.cloud/
   - EzCaptcha: https://ez-captcha.com/
   - CapSolver: https://capsolver.com/

3. **Restart the service**

### Solution 2: Fix Browser Captcha Service

If you prefer to use the browser method:

1. **Check Playwright installation**:
   ```bash
   python -m playwright install chromium
   ```

2. **Fix event loop policy** - The code already has this, but ensure it's working:
   ```python
   if sys.platform == 'win32':
       asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
   ```

3. **Check browser_captcha.py** for Windows compatibility issues

### Solution 3: Reset Token Error Counts

Reset the consecutive error counts via admin panel or database:

1. Access admin panel: http://localhost:18282/admin
2. Navigate to token management
3. Reset error counts for both tokens
4. Ensure Token #1 is enabled if needed

### Solution 4: Add Fresh Tokens

Add new Google accounts with fresh session tokens that haven't accumulated errors.

## Testing

After applying the fix, test with:

```bash
# Enable debug mode (already enabled)
# Run test
python debug_image_test.py

# Or test the API directly
python test_generate_api.py

# Check logs
tail -50 logs.txt
```

## Files Created for Debugging

1. **debug_image_test.py** - End-to-end image generation test with colored output
2. **test_generate_api.py** - Direct API function test with detailed logging
3. **diagnose_tokens.py** - Token health diagnostic tool

## Request Flow

```
User Request
    ↓
Generation Handler (generation_handler.py:450)
    ↓
Flow Client (flow_client.py:360-428)
    ↓
_get_recaptcha_token (flow_client.py:769-795)
    ↓
BrowserCaptchaService (browser_captcha.py)
    ↓
❌ Browser fails to start (NotImplementedError)
    ↓
Returns empty reCAPTCHA token ("")
    ↓
API Request with empty token
    ↓
Google API rejects: HTTP 403 - reCAPTCHA evaluation failed
```

## Configuration Files

- **config/setting.toml** - Main configuration
  - `[debug]` section - Now enabled for logging
  - `[captcha]` section - Currently set to "browser"
  
- **logs.txt** - Debug logs showing all HTTP requests/responses

## Recommendation

**Immediately switch to YesCaptcha or another API-based captcha service** as the browser-based solution has compatibility issues on your Windows environment. This is the quickest path to resolution.

Cost: Most captcha services charge $1-3 per 1000 captchas, which is very reasonable for API usage.
