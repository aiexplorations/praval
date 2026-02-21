#!/usr/bin/env python3
"""
Test runner for all executable Praval Python examples.

This script discovers executable .py files under examples/ (excluding
non-Python assets) and runs each with a timeout to prevent hangs.
"""

import subprocess
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def run_with_timeout(cmd, timeout=30):
    """Run a command with timeout and capture output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/Users/rajesh/Github/praval",
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT: Process took longer than 30 seconds"
    except Exception as e:
        return -2, "", f"ERROR: {str(e)}"


def run_single_example(example_file):
    """Run a single example file and check if it passes."""
    print(f"\n🧪 Testing {example_file}...")

    # Run the example
    cmd = [sys.executable, f"examples/{example_file}"]

    returncode, stdout, stderr = run_with_timeout(cmd, timeout=45)

    if returncode == 0:
        print(f"✅ {example_file} - PASSED")
        if stdout.strip():
            print(f"   📄 Output preview: {stdout.strip()[:200]}...")
        return True
    elif returncode == -1:
        print(f"⏰ {example_file} - TIMEOUT (may be working but taking too long)")
        return False
    else:
        print(f"❌ {example_file} - FAILED (exit code: {returncode})")
        if stderr.strip():
            print(f"   🔍 Error: {stderr.strip()[:300]}...")
        if stdout.strip():
            print(f"   📄 Output: {stdout.strip()[:200]}...")
        return False


def main():
    """Test all examples in the examples directory."""
    print("🚀 Testing all Praval v0.7.22 examples...")
    print("=" * 60)

    examples_dir = Path("/Users/rajesh/Github/praval/examples")

    # Discover all executable python examples recursively.
    # Skip __pycache__ and hidden paths.
    example_paths = []
    for path in examples_dir.rglob("*.py"):
        parts = path.parts
        if "__pycache__" in parts:
            continue
        if any(part.startswith(".") for part in parts):
            continue
        example_paths.append(path)

    # Sort by relative path for deterministic order
    example_paths = sorted(
        example_paths, key=lambda p: str(p.relative_to(examples_dir))
    )
    example_files = [str(p.relative_to(examples_dir)) for p in example_paths]

    print(f"Found {len(example_files)} examples to test:")
    for ef in example_files:
        print(f"  📝 {ef}")

    print("\n" + "=" * 60)

    # Test each example
    results = {}
    passed = 0
    failed = 0

    for example_file in example_files:
        try:
            success = run_single_example(example_file)
            results[example_file] = success
            if success:
                passed += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            print("\n⚠️ Testing interrupted by user")
            break
        except Exception as e:
            print(f"❌ Unexpected error testing {example_file}: {e}")
            results[example_file] = False
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)

    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(
        f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%"
        if (passed + failed) > 0
        else "N/A"
    )

    print("\n📋 Detailed Results:")
    for example, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {example}")

    if failed > 0:
        print(f"\n⚠️ {failed} examples need attention!")
        return False
    else:
        print("\n🎉 All examples are working correctly!")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
