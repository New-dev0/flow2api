"""
Fix for Playwright NotImplementedError on Windows

This script patches the browser_captcha.py to work on Windows by:
1. Using ProactorEventLoop instead of SelectorEventLoop for Playwright
2. Adding proper Windows-specific subprocess handling
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def create_patched_browser_captcha():
    """Create a patched version of browser_captcha.py"""
    
    patch_code = '''"""
浏览器自动化获取 reCAPTCHA token - Windows 兼容版本
使用 Playwright 访问页面并执行 reCAPTCHA 验证
"""
import asyncio
import time
import re
import sys
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext

from ..core.logger import debug_logger


def parse_proxy_url(proxy_url: str) -> Optional[Dict[str, str]]:
    """解析代理URL，分离协议、主机、端口、认证信息

    Args:
        proxy_url: 代理URL，格式：protocol://[username:password@]host:port

    Returns:
        代理配置字典，包含server、username、password（如果有认证）
    """
    proxy_pattern = r'^(socks5|http|https)://(?:([^:]+):([^@]+)@)?([^:]+):(\\d+)$'
    match = re.match(proxy_pattern, proxy_url)

    if match:
        protocol, username, password, host, port = match.groups()
        proxy_config = {'server': f'{protocol}://{host}:{port}'}

        if username and password:
            proxy_config['username'] = username
            proxy_config['password'] = password

        return proxy_config
    return None


def validate_browser_proxy_url(proxy_url: str) -> tuple[bool, str]:
    """验证浏览器代理URL格式（仅支持HTTP和无认证SOCKS5）

    Args:
        proxy_url: 代理URL

    Returns:
        (是否有效, 错误信息)
    """
    if not proxy_url or not proxy_url.strip():
        return True, ""  # 空URL视为有效（不使用代理）

    proxy_url = proxy_url.strip()
    parsed = parse_proxy_url(proxy_url)

    if not parsed:
        return False, "代理URL格式错误，正确格式：http://host:port 或 socks5://host:port"

    # 检查是否有认证信息
    has_auth = 'username' in parsed

    # 获取协议
    protocol = parsed['server'].split('://')[0]

    # SOCKS5不支持认证
    if protocol == 'socks5' and has_auth:
        return False, "浏览器不支持带认证的SOCKS5代理，请使用HTTP代理或移除SOCKS5认证"

    # HTTP/HTTPS支持认证
    if protocol in ['http', 'https']:
        return True, ""

    # SOCKS5无认证支持
    if protocol == 'socks5' and not has_auth:
        return True, ""

    return False, f"不支持的代理协议：{protocol}"


class BrowserCaptchaService:
    """浏览器自动化获取 reCAPTCHA token（单例模式）- Windows 兼容版本"""

    _instance: Optional['BrowserCaptchaService'] = None
    _lock = asyncio.Lock()

    def __init__(self, db=None):
        """初始化服务（始终使用无头模式）"""
        self.headless = True  # 始终无头
        self.playwright = None
        self.browser: Optional[Browser] = None
        self._initialized = False
        self.website_key = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
        self.db = db
        self._original_loop_policy = None

    @classmethod
    async def get_instance(cls, db=None) -> 'BrowserCaptchaService':
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db)
                    await cls._instance.initialize()
        return cls._instance

    def _setup_windows_event_loop(self):
        """为 Windows 设置正确的事件循环策略"""
        if sys.platform == 'win32':
            try:
                # 保存当前策略
                self._original_loop_policy = asyncio.get_event_loop_policy()
                
                # 使用 ProactorEventLoop（支持子进程）
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                debug_logger.log_info("[BrowserCaptcha] Windows: 已切换到 ProactorEventLoop")
            except Exception as e:
                debug_logger.log_warning(f"[BrowserCaptcha] 无法切换事件循环: {e}")

    def _restore_event_loop(self):
        """恢复原始事件循环策略"""
        if sys.platform == 'win32' and self._original_loop_policy:
            try:
                asyncio.set_event_loop_policy(self._original_loop_policy)
                debug_logger.log_info("[BrowserCaptcha] 已恢复原始事件循环策略")
            except Exception as e:
                debug_logger.log_warning(f"[BrowserCaptcha] 无法恢复事件循环: {e}")

    async def initialize(self):
        """初始化浏览器（启动一次）"""
        if self._initialized:
            return

        try:
            # Windows: 切换到 ProactorEventLoop
            self._setup_windows_event_loop()

            # 获取浏览器专用代理配置
            proxy_url = None
            if self.db:
                captcha_config = await self.db.get_captcha_config()
                if captcha_config.browser_proxy_enabled and captcha_config.browser_proxy_url:
                    proxy_url = captcha_config.browser_proxy_url

            debug_logger.log_info(f"[BrowserCaptcha] 正在启动浏览器... (proxy={proxy_url or 'None'})")
            self.playwright = await async_playwright().start()

            # 配置浏览器启动参数
            launch_options = {
                'headless': self.headless,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            }

            # 如果有代理，解析并添加代理配置
            if proxy_url:
                proxy_config = parse_proxy_url(proxy_url)
                if proxy_config:
                    launch_options['proxy'] = proxy_config
                    auth_info = "auth=yes" if 'username' in proxy_config else "auth=no"
                    debug_logger.log_info(f"[BrowserCaptcha] 代理配置: {proxy_config['server']} ({auth_info})")
                else:
                    debug_logger.log_warning(f"[BrowserCaptcha] 代理URL格式错误: {proxy_url}")

            self.browser = await self.playwright.chromium.launch(**launch_options)
            self._initialized = True
            debug_logger.log_info(f"[BrowserCaptcha] ✅ 浏览器已启动 (headless={self.headless}, proxy={proxy_url or 'None'})")
        except Exception as e:
            debug_logger.log_error(f"[BrowserCaptcha] ❌ 浏览器启动失败: {str(e)}")
            # 恢复事件循环
            self._restore_event_loop()
            raise

    async def get_token(self, project_id: str) -> Optional[str]:
        """获取 reCAPTCHA token

        Args:
            project_id: Flow项目ID

        Returns:
            reCAPTCHA token字符串，如果获取失败返回None
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        context = None

        try:
            # 创建新的上下文
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York'
            )
            page = await context.new_page()

            website_url = f"https://labs.google/fx/tools/flow/project/{project_id}"

            debug_logger.log_info(f"[BrowserCaptcha] 访问页面: {website_url}")

            # 访问页面
            try:
                await page.goto(website_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                debug_logger.log_warning(f"[BrowserCaptcha] 页面加载超时或失败: {str(e)}")

            # 检查并注入 reCAPTCHA v3 脚本
            debug_logger.log_info("[BrowserCaptcha] 检查并加载 reCAPTCHA v3 脚本...")
            script_loaded = await page.evaluate("""
                () => {
                    if (window.grecaptcha && typeof window.grecaptcha.execute === 'function') {
                        return true;
                    }
                    return false;
                }
            """)

            if not script_loaded:
                # 注入脚本
                debug_logger.log_info("[BrowserCaptcha] 注入 reCAPTCHA v3 脚本...")
                await page.evaluate(f"""
                    () => {{
                        return new Promise((resolve) => {{
                            const script = document.createElement('script');
                            script.src = 'https://www.google.com/recaptcha/api.js?render={self.website_key}';
                            script.async = true;
                            script.defer = true;
                            script.onload = () => {{
                                console.log('reCAPTCHA script loaded');
                                resolve(true);
                            }};
                            script.onerror = () => {{
                                console.error('Failed to load reCAPTCHA script');
                                resolve(false);
                            }};
                            document.head.appendChild(script);
                        }});
                    }}
                """)

                # 等待脚本加载和初始化
                await asyncio.sleep(3)

            # 执行 reCAPTCHA 获取 token
            debug_logger.log_info("[BrowserCaptcha] 执行 reCAPTCHA...")
            token = await page.evaluate(f"""
                () => {{
                    return new Promise((resolve) => {{
                        if (!window.grecaptcha || typeof window.grecaptcha.execute !== 'function') {{
                            console.error('grecaptcha.execute is not available');
                            resolve(null);
                            return;
                        }}
                        
                        window.grecaptcha.ready(() => {{
                            window.grecaptcha.execute('{self.website_key}', {{
                                action: 'FLOW_GENERATION'
                            }}).then((token) => {{
                                console.log('Got reCAPTCHA token:', token.substring(0, 20) + '...');
                                resolve(token);
                            }}).catch((error) => {{
                                console.error('reCAPTCHA error:', error);
                                resolve(null);
                            }});
                        }});
                    }});
                }}
            """)

            duration = time.time() - start_time

            if token:
                debug_logger.log_info(f"[BrowserCaptcha] ✅ Token获取成功 (耗时: {duration:.2f}s, token前20字符: {token[:20]}...)")
                return token
            else:
                debug_logger.log_warning(f"[BrowserCaptcha] ❌ Token获取失败 (耗时: {duration:.2f}s)")
                return None

        except Exception as e:
            duration = time.time() - start_time
            debug_logger.log_error(f"[BrowserCaptcha] ❌ 获取Token时发生异常 (耗时: {duration:.2f}s): {str(e)}")
            return None
        finally:
            # 清理上下文
            if context:
                try:
                    await context.close()
                except Exception as e:
                    debug_logger.log_warning(f"[BrowserCaptcha] 关闭上下文失败: {str(e)}")

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            try:
                await self.browser.close()
                debug_logger.log_info("[BrowserCaptcha] 浏览器已关闭")
            except Exception as e:
                debug_logger.log_error(f"[BrowserCaptcha] 关闭浏览器失败: {str(e)}")
            finally:
                self.browser = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                debug_logger.log_error(f"[BrowserCaptcha] 停止Playwright失败: {str(e)}")
            finally:
                self.playwright = None
        
        self._initialized = False
        
        # 恢复事件循环
        self._restore_event_loop()

    def __del__(self):
        """析构函数"""
        if self._initialized:
            try:
                # 尝试清理资源
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
            except:
                pass
'''
    
    return patch_code

def apply_patch():
    """Apply the patch to browser_captcha.py"""
    import shutil
    from pathlib import Path
    
    # Paths
    original_file = Path(__file__).parent / "src" / "services" / "browser_captcha.py"
    backup_file = Path(__file__).parent / "src" / "services" / "browser_captcha.py.backup"
    
    print("Windows Playwright Fix - Browser Captcha Patch")
    print("=" * 60)
    
    # Check if original exists
    if not original_file.exists():
        print(f"ERROR: {original_file} not found!")
        return False
    
    # Create backup
    print(f"\n1. Creating backup: {backup_file.name}")
    shutil.copy2(original_file, backup_file)
    print("   OK: Backup created")
    
    # Read original to preserve the rest of the file
    with open(original_file, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # Check if already patched
    if 'WindowsProactorEventLoopPolicy' in original_content:
        print("\n   Already patched! No changes needed.")
        return True
    
    # Write patched version
    print("\n2. Applying patch...")
    patched_content = create_patched_browser_captcha()
    
    with open(original_file, 'w', encoding='utf-8') as f:
        f.write(patched_content)
    
    print("   OK: Patch applied")
    
    print("\n3. Summary:")
    print("   - Original file backed up to: browser_captcha.py.backup")
    print("   - Patched file written")
    print("   - Changes:")
    print("     * Added WindowsProactorEventLoopPolicy support")
    print("     * Added event loop switching on Windows")
    print("     * Added proper cleanup/restore")
    
    print("\n" + "=" * 60)
    print("SUCCESS: Patch applied successfully!")
    print("\nNext steps:")
    print("1. Restart your Flow2API server")
    print("2. Test image generation: python debug_image_test.py")
    print("\nTo revert: Copy browser_captcha.py.backup back to browser_captcha.py")
    
    return True

if __name__ == '__main__':
    try:
        success = apply_patch()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: Patch failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
