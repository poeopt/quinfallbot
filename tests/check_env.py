import sys
import os
try:
    from scapy.all import conf, get_if_list
    import scapy
    scapy_available = True
except ImportError:
    scapy_available = False

def check_admin():
    try:
        # Windows check
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        # Unix-like check
        return os.getuid() == 0
    except Exception:
        return False

def main():
    print("=== Quinfall Bot Environment Check ===")

    # 1. Admin/Root Check
    is_admin = check_admin()
    print(f"Administrative privileges: {'YES' if is_admin else 'NO'}")
    if not is_admin:
        print("WARNING: Scapy requires administrative privileges to sniff packets on most systems.")

    # 2. Scapy Check
    if scapy_available:
        print(f"Scapy version: {scapy.VERSION}")
        # 3. Backend Check
        # Scapy uses different backends, let's try to see if it's using Npcap/WinPcap or something else
        try:
            from scapy.arch.windows import get_windows_if_list
            print("Running on Windows.")
        except ImportError:
            pass

        # 4. Interfaces
        print("\nAvailable Interfaces:")
        try:
            ifaces = conf.ifaces.values()
            for i in ifaces:
                print(f" - {i}")
            if not ifaces:
                print(" No interfaces found via conf.ifaces.")
        except Exception as e:
            print(f" Error listing interfaces: {e}")

    else:
        print("Scapy is NOT installed or not in PYTHONPATH.")

    print("\nCheck complete.")

if __name__ == "__main__":
    main()
