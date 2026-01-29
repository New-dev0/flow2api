# Windows Playwright NotImplementedError - Solutions

## Problem
Playwright on Windows fails with `NotImplementedError` when using `WindowsSelectorEventLoopPolicy` because it doesn't support subprocess creation.

```
NotImplementedError at asyncio.base_events.py:503 in _make_subprocess_transport
```

## Solutions (Choose One)

### Solution 1: Apply the Patch (Recommended for Browser Method)

Run the patch script to fix browser_captcha.py:

```bash
python fix_playwright_windows.py
```

This will:
- Backup the original file
- Patch browser_captcha.py to use `WindowsProactorEventLoopPolicy`
- Add proper event loop switching for Windows

**What it does:**
- Switches to ProactorEventLoop before starting Playwright
- Restores original event loop after closing
- Maintains compatibility with the rest of the application

### Solution 2: Use API-based Captcha (Easiest)

Switch to an API captcha service instead of browser automation:

**Edit `config/setting.toml`:**
```toml
[captcha]
captcha_method = "yescaptcha"  # or capmonster, ezcaptcha, capsolver
yescaptcha_api_key = "YOUR_API_KEY_HERE"
yescaptcha_base_url = "https://api.yescaptcha.com"
```

**Services:**
- YesCaptcha: https://yescaptcha.com/ (~$1-2 per 1000 captchas)
- CapMonster: https://capmonster.cloud/
- EzCaptcha: https://ez-captcha.com/
- CapSolver: https://capsolver.com/

### Solution 3: Manual Event Loop Fix

If you want to manually edit the code, add this to `browser_captcha.py`:

**In the `initialize` method, before starting Playwright:**

```python
async def initialize(self):
    if self._initialized:
        return

    try:
        # FIX: Switch to ProactorEventLoop on Windows
        if sys.platform == 'win32':
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            debug_logger.log_info("[BrowserCaptcha] Windows: switched to ProactorEventLoop")
        
        # ... rest of the initialization code
```

**In the `close` method, restore the policy:**

```python
async def close(self):
    # ... existing close code ...
    
    # FIX: Restore original event loop policy on Windows
    if sys.platform == 'win32':
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

### Solution 4: Install Chrome/Chromium Manually

Sometimes Playwright fails because it can't find the browser:

```bash
# Install Playwright browsers
python -m playwright install chromium

# Or install all browsers
python -m playwright install
```

## Testing After Fix

Test the fix with:

```bash
# Test image generation
python debug_image_test.py

# Check logs
tail -50 logs.txt
```

## Expected Behavior After Fix

In `logs.txt`, you should see:

```
[BrowserCaptcha] Windows: 已切换到 ProactorEventLoop
[BrowserCaptcha] ✅ 浏览器已启动
[BrowserCaptcha] ✅ Token获取成功
```

And in the request:

```json
{
  "clientContext": {
    "recaptchaToken": "03AL8dmw9Vm7d...",  // ← No longer empty!
    "sessionId": ";1769409971480"
  }
}
```

## Comparison

| Solution | Pros | Cons |
|----------|------|------|
| **Patch Script** | Automated, clean, maintains browser method | Requires file modification |
| **API Service** | No code changes, reliable, fast | Costs $1-3 per 1000 captchas |
| **Manual Fix** | Full control | More work, error-prone |
| **Install Browsers** | May fix detection issues | Might not fix subprocess issue |

## Recommendation

1. **For production**: Use API service (Solution 2) - most reliable
2. **For development/testing**: Apply patch (Solution 1) - free
3. **Quick test**: Try installing browsers (Solution 4) first

## Why This Happens

Windows has two event loop implementations:
- **SelectorEventLoop**: Used by FastAPI, doesn't support subprocesses
- **ProactorEventLoop**: Supports subprocesses (needed by Playwright)

The application uses SelectorEventLoop by default for FastAPI compatibility, but Playwright needs ProactorEventLoop to launch browser subprocesses.

The patch temporarily switches the event loop for browser operations, then switches back.
