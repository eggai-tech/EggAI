#!/usr/bin/env python3
"""
Test runner for EggAI projects.
Automatically discovers and runs tests in the SDK and all example directories.
"""
import os
import sys
import glob
import subprocess

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def install_requirements(directory):
    """Install requirements.txt if it exists in the directory."""
    req_file = os.path.join(directory, "requirements.txt")
    venv_dir = os.path.join(directory, ".venv")
    
    if os.path.exists(req_file):
        print(f"Installing dependencies from {req_file} in virtual environment...")
        
        # Create virtual environment if it doesn't exist
        if not os.path.exists(venv_dir):
            print(f"Creating virtual environment in {venv_dir}...")
            subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        
        # Get path to pip in the virtual environment
        if sys.platform == "win32":
            pip_path = os.path.join(venv_dir, "Scripts", "pip")
        else:
            pip_path = os.path.join(venv_dir, "bin", "pip")
        
        # Install requirements
        subprocess.check_call([pip_path, "install", "-r", req_file])

def run_tests(directory, pattern="test_*.py"):
    """Run pytest in the specified directory using the virtual environment."""
    orig_dir = os.getcwd()
    try:
        os.chdir(directory)
        print(f"Running tests in {directory}...")
        
        # Use pytest from the virtual environment
        venv_dir = os.path.join(directory, ".venv")
        if sys.platform == "win32":
            pytest_path = os.path.join(venv_dir, "Scripts", "pytest")
        else:
            pytest_path = os.path.join(venv_dir, "bin", "pytest")
        
        # Install pytest if it's not already installed
        if not os.path.exists(pytest_path):
            if sys.platform == "win32":
                pip_path = os.path.join(venv_dir, "Scripts", "pip")
            else:
                pip_path = os.path.join(venv_dir, "bin", "pip")
            subprocess.check_call([pip_path, "install", "pytest"])
        
        # Run the tests
        result = subprocess.run([pytest_path, "-v"])
        return result.returncode
    finally:
        os.chdir(orig_dir)

def run_sdk_tests():
    """Run tests for the SDK."""
    sdk_dir = os.path.join(ROOT_DIR, "sdk")
    install_requirements(sdk_dir)
    return run_tests(sdk_dir)

def discover_examples():
    """Discover all example directories."""
    examples_dir = os.path.join(ROOT_DIR, "examples")
    return [d for d in glob.glob(os.path.join(examples_dir, "*")) 
            if os.path.isdir(d) and has_tests(d)]

def has_tests(directory):
    """Check if directory has tests."""
    test_dir = os.path.join(directory, "tests")
    if os.path.isdir(test_dir) and glob.glob(os.path.join(test_dir, "test_*.py")):
        return True
    
    # Check for nested test directories
    for root, dirs, files in os.walk(directory):
        if "tests" in dirs:
            test_path = os.path.join(root, "tests")
            if glob.glob(os.path.join(test_path, "test_*.py")):
                return True
    
    return False

def run_example_tests(example_dir, print_summary=False):
    """Run tests for a specific example."""
    example_name = os.path.basename(example_dir)
    test_files = glob.glob(os.path.join(example_dir, "tests", "test_*.py"))
    
    # Install dependencies
    install_requirements(example_dir)
    
    # Run tests
    result = run_tests(example_dir)
    
    # Print summary if requested
    if print_summary:
        status_color = {
            "success": "\033[92m",  # Green
            "failure": "\033[91m",  # Red
        }
        reset_color = "\033[0m"
        
        status = "success" if result == 0 else "failure"
        
        print("\n" + "="*60)
        print(f" TEST SUMMARY FOR {example_name.upper()}")
        print("="*60)
        print(f"Status: {status_color.get(status, '')}{status.upper()}{reset_color}")
        print(f"Test files found: {len(test_files)}")
        print("="*60)
        
    return result

def sdk():
    """Run SDK tests."""
    return run_sdk_tests()

def run_all():
    """Run all tests in SDK and examples."""
    failures = 0
    test_results = {
        "sdk": {"status": "not_run", "message": "", "tests_run": 0},
        "examples": {}
    }
    
    # Run SDK tests
    print("== Running SDK Tests ==")
    try:
        sdk_result = run_sdk_tests()
        test_results["sdk"]["status"] = "success" if sdk_result == 0 else "failure" 
        test_results["sdk"]["tests_run"] = 1
        failures += sdk_result > 0
    except Exception as e:
        error_msg = f"Error running SDK tests: {e}"
        print(error_msg)
        test_results["sdk"]["status"] = "error"
        test_results["sdk"]["message"] = str(e)
        failures += 1
    
    # Run tests for each example
    examples = discover_examples()
    for example in examples:
        example_name = os.path.basename(example)
        print(f"\n== Running Tests for {example_name} ==")
        
        test_results["examples"][example_name] = {
            "status": "not_run", 
            "message": "",
            "tests_run": 0
        }
        
        # Check if tests exist before running
        test_files = glob.glob(os.path.join(example, "tests", "test_*.py"))
        if not test_files:
            print(f"ℹ️  No tests found for {example_name}")
            test_results["examples"][example_name]["status"] = "skipped"
            test_results["examples"][example_name]["message"] = "No tests found"
            continue
            
        try:
            example_result = run_example_tests(example)
            test_results["examples"][example_name]["status"] = "success" if example_result == 0 else "failure"
            test_results["examples"][example_name]["tests_run"] = len(test_files)
            failures += example_result > 0
        except Exception as e:
            error_msg = f"Error running tests for {example_name}: {e}"
            print(error_msg)
            test_results["examples"][example_name]["status"] = "error"
            test_results["examples"][example_name]["message"] = str(e)
            failures += 1
    
    # Print summary
    print("\n" + "="*60)
    print(" "*20 + "TEST RUN SUMMARY")
    print("="*60)
    
    print("\nSDK Tests:")
    sdk_status = test_results["sdk"]["status"]
    status_color = {
        "success": "\033[92m",  # Green
        "failure": "\033[91m",  # Red
        "error": "\033[91m",    # Red
        "skipped": "\033[93m",  # Yellow
        "not_run": "\033[93m"   # Yellow
    }
    reset_color = "\033[0m"
    
    print(f"  Status: {status_color.get(sdk_status, '')}{sdk_status.upper()}{reset_color}")
    if test_results["sdk"]["message"]:
        print(f"  Message: {test_results['sdk']['message']}")
    
    print("\nExample Tests:")
    example_count = len(test_results["examples"])
    success_count = sum(1 for ex in test_results["examples"].values() if ex["status"] == "success")
    failure_count = sum(1 for ex in test_results["examples"].values() if ex["status"] == "failure")
    error_count = sum(1 for ex in test_results["examples"].values() if ex["status"] == "error")
    skipped_count = sum(1 for ex in test_results["examples"].values() if ex["status"] == "skipped")
    
    print(f"  Total Examples: {example_count}")
    print(f"  {status_color.get('success', '')}Success: {success_count}{reset_color}")
    print(f"  {status_color.get('failure', '')}Failures: {failure_count}{reset_color}")
    print(f"  {status_color.get('error', '')}Errors: {error_count}{reset_color}")
    print(f"  {status_color.get('skipped', '')}Skipped: {skipped_count}{reset_color}")
    
    if failures:
        print(f"\n{status_color.get('failure', '')}FAILED EXAMPLES:{reset_color}")
        for example_name, result in test_results["examples"].items():
            if result["status"] in ["failure", "error"]:
                print(f"  - {example_name}: {result['status'].upper()}")
                if result["message"]:
                    print(f"    {result['message']}")
    
    print("\n" + "="*60)
    return failures

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "sdk":
            sys.exit(sdk())
        elif sys.argv[1] == "all":
            sys.exit(run_all())
        else:
            # Check if it's a specific example
            example_name = sys.argv[1]
            example_path = os.path.join(ROOT_DIR, "examples", example_name)
            if os.path.isdir(example_path):
                sys.exit(run_example_tests(example_path, print_summary=True))
            else:
                print(f"Unknown test target: {example_name}")
                sys.exit(1)
    else:
        # Default to running all tests
        sys.exit(run_all())