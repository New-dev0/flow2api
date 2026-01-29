"""
Token Diagnostic Tool
Checks the status of tokens in the database and tests their validity

Usage:
    python diagnose_tokens.py
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.database import Database
from src.services.flow_client import FlowClient
from src.services.proxy_manager import ProxyManager
from src.services.token_manager import TokenManager
from src.core.config import config
from datetime import datetime

async def diagnose():
    """Diagnose token issues"""
    
    print("="*80)
    print("Token Diagnostics Tool")
    print("="*80)
    print()
    
    # Initialize services
    print("[1/5] Initializing database...")
    db = Database()
    await db.init_db()
    
    print("[2/5] Initializing proxy manager...")
    proxy_manager = ProxyManager(db)
    
    print("[3/5] Initializing Flow client...")
    flow_client = FlowClient(proxy_manager, db)
    
    print("[4/5] Initializing token manager...")
    token_manager = TokenManager(db, flow_client)
    
    print("[5/5] Loading tokens from database...")
    tokens = await db.get_all_tokens()
    
    print(f"\nFound {len(tokens)} token(s) in database\n")
    
    if not tokens:
        print("ERROR No tokens found in database!")
        print("\nPlease add tokens via the admin panel:")
        print(f"  http://{config.server_host}:{config.server_port}/admin")
        return
    
    # Check each token
    for idx, token in enumerate(tokens, 1):
        print(f"{'='*80}")
        print(f"Token #{idx}: {token.email or 'N/A'}")
        print(f"{'='*80}")
        print(f"ID: {token.id}")
        print(f"Email: {token.email or 'N/A'}")
        print(f"Active: {token.is_active}")
        print(f"Image Enabled: {token.image_enabled}")
        print(f"Video Enabled: {token.video_enabled}")
        print(f"Credits: {token.credits}")
        print(f"User Tier: {token.user_paygate_tier}")
        print(f"Current Project ID: {token.current_project_id or 'Not set'}")
        print(f"Ban Reason: {token.ban_reason or 'None'}")
        
        # Check expiry
        if token.at_expires:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            # Make sure at_expires is timezone-aware
            at_expires = token.at_expires
            if at_expires.tzinfo is None:
                at_expires = at_expires.replace(tzinfo=timezone.utc)
            
            if now < at_expires:
                remaining = at_expires - now
                print(f"AT Expires: {at_expires} (in {remaining.total_seconds()/3600:.1f} hours)")
            else:
                print(f"AT Expires: {at_expires} (EXPIRED)")
        else:
            print("AT Expires: Not set")
        
        print()
        
        # Test ST to AT conversion
        if token.st:
            print("Testing ST -> AT conversion...")
            try:
                result = await flow_client.st_to_at(token.st)
                print(f"OK ST is valid")
                print(f"  AT: {result['access_token'][:30]}...")
                print(f"  Expires: {result['expires']}")
                
                if result.get('user'):
                    user = result['user']
                    print(f"  User Email: {user.get('email', 'N/A')}")
                    print(f"  User Name: {user.get('name', 'N/A')}")
                
            except Exception as e:
                print(f"FAIL ST validation failed: {e}")
        else:
            print("WARNING No ST token set")
        
        print()
        
        # Test AT
        if token.at:
            print("Testing AT (checking credits)...")
            try:
                result = await flow_client.get_credits(token.at)
                print(f"OK AT is valid")
                print(f"  Credits: {result.get('credits', 0)}")
                print(f"  Tier: {result.get('userPaygateTier', 'UNKNOWN')}")
            except Exception as e:
                print(f"FAIL AT validation failed: {e}")
                
                # Try to refresh AT from ST
                if token.st:
                    print("\nAttempting to refresh AT from ST...")
                    try:
                        success = await token_manager.refresh_at(token.id)
                        if success:
                            print("OK AT refreshed successfully")
                            
                            # Re-test
                            token = await db.get_token(token.id)
                            result = await flow_client.get_credits(token.at)
                            print(f"OK New AT is valid")
                            print(f"  Credits: {result.get('credits', 0)}")
                            print(f"  Tier: {result.get('userPaygateTier', 'UNKNOWN')}")
                        else:
                            print("FAIL Failed to refresh AT")
                    except Exception as e2:
                        print(f"FAIL AT refresh failed: {e2}")
        else:
            print("WARNING No AT token set")
        
        print()
        
        # Test project
        if token.current_project_id:
            print(f"Project ID: {token.current_project_id}")
            print("  (Cannot test project without making API calls)")
        else:
            print("WARNING No project ID set")
            
            if token.at and token.st:
                print("  Attempting to create project...")
                try:
                    await token_manager.ensure_project_exists(token.id)
                    token = await db.get_token(token.id)
                    print(f"OK Project created: {token.current_project_id}")
                except Exception as e:
                    print(f"FAIL Project creation failed: {e}")
        
        print()
        
        # Summary
        print("Summary:")
        issues = []
        
        # Get token stats
        try:
            stats = await db.get_token_stats(token.id)
            if stats and stats.consecutive_error_count >= 3:
                issues.append(f"High consecutive error count ({stats.consecutive_error_count})")
        except:
            pass
        
        if not token.is_active:
            issues.append("Token is disabled")
        if token.ban_reason:
            issues.append(f"Token is banned: {token.ban_reason}")
        if not token.st:
            issues.append("No ST token")
        if not token.at:
            issues.append("No AT token")
        if token.at_expires:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            at_expires = token.at_expires
            if at_expires.tzinfo is None:
                at_expires = at_expires.replace(tzinfo=timezone.utc)
            if now > at_expires:
                issues.append("AT expired")
        if not token.current_project_id:
            issues.append("No project ID")
        if token.credits == 0:
            issues.append("No credits")
        
        if issues:
            print("ERROR Issues found:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("OK Token appears healthy")
        
        print()
    
    print("="*80)
    print("Diagnostic Complete")
    print("="*80)
    
    await db.close()

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(diagnose())
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted by user")
        sys.exit(130)
