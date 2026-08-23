import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from application.platform_controller import PlatformController

def main():
    print("==================================================")
    print("              Starting PacketForge                ")
    print("==================================================")
    
    # 1. Initialize Platform Controller
    platform = PlatformController()
    
    # 2. Initialize and Register Subsystems
    platform.initialize_components()
    
    # 3. Boot Server Daemons (DHCP, DNS, Proxy, Search API)
    try:
        platform.boot()
        
        # 4. Launch Main UI
        platform.launch_uis()
    except KeyboardInterrupt:
        print("\n[PacketForge] Shutdown signal received.")
    finally:
        # 5. Graceful Shutdown
        platform.shutdown()

if __name__ == "__main__":
    main()
