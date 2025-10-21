#!/usr/bin/env python3
"""
Quick test to verify all imports work
"""

print("Testing imports...")

try:
    print("✓ Importing app modules...")
    from app import __version__
    print(f"  Version: {__version__}")

    print("✓ Importing radius_tools...")
    from app.radius_tools import ALL_TOOLS
    print(f"  Found {len(ALL_TOOLS)} tools")

    print("✓ Importing function_handler...")
    from app.function_handler import FunctionHandler, create_realtime_function_definitions
    print(f"  Found {len(create_realtime_function_definitions())} function definitions")

    print("\n✅ All basic imports successful!")
    print("\nNote: Some imports require dependencies from requirements.txt")
    print("Run: pip install -r requirements.txt")

except ImportError as e:
    print(f"\n❌ Import error: {e}")
    print("\nMissing dependencies. Install with:")
    print("pip install -r requirements.txt")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
