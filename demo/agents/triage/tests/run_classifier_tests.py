#!/usr/bin/env python3
"""Comprehensive test runner for classifier v6 and v7 tests."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class ClassifierTestRunner:
    """Test runner for classifier test suites."""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.project_root = project_root
        
    def run_command(self, cmd, description=""):
        """Run a command and return success status."""
        print(f"\n{'='*60}")
        if description:
            print(f"Running: {description}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(cmd, capture_output=False, text=True, cwd=self.project_root)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running command: {e}")
            return False
    
    def check_dependencies(self):
        """Check if required dependencies are available."""
        print("Checking dependencies...")
        
        required_packages = [
            'pytest', 'mlflow', 'numpy', 'dotenv', 'torch', 
            'transformers', 'peft', 'datasets', 'dspy'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
                print(f"✓ {package}")
            except ImportError:
                print(f"✗ {package} (missing)")
                missing_packages.append(package)
        
        if missing_packages:
            print(f"\nMissing packages: {', '.join(missing_packages)}")
            print("Install with: pip install " + " ".join(missing_packages))
            return False
        
        return True
    
    def run_unit_tests(self):
        """Run unit tests for both classifiers."""
        print("\n🧪 Running Unit Tests")
        
        unit_test_files = [
            "test_classifier_v6_comprehensive.py",
            "test_classifier_v7_comprehensive.py"
        ]
        
        success = True
        for test_file in unit_test_files:
            cmd = ["python", "-m", "pytest", f"agents/triage/tests/{test_file}", "-v", "--tb=short"]
            if not self.run_command(cmd, f"Unit tests: {test_file}"):
                success = False
        
        return success
    
    def run_integration_tests(self):
        """Run integration tests."""
        print("\n🔗 Running Integration Tests")
        
        # Check environment variables for integration tests
        v6_ready = bool(os.getenv('OPENAI_API_KEY') and os.getenv('TRIAGE_CLASSIFIER_V6_MODEL_ID'))
        v7_ready = True  # V7 can always run with base model
        
        print(f"V6 integration ready: {v6_ready}")
        print(f"V7 integration ready: {v7_ready}")
        
        integration_tests = []
        
        if v6_ready:
            integration_tests.extend([
                ("test_classifier_v6.py", "V6 Full Integration"),
                ("test_classifier_v6_comprehensive.py::TestClassifierV6Integration", "V6 Unit Integration")
            ])
        
        if v7_ready:
            integration_tests.extend([
                ("test_classifier_v7.py", "V7 Full Integration"), 
                ("test_classifier_v7_comprehensive.py::TestClassifierV7Integration", "V7 Unit Integration")
            ])
        
        success = True
        for test_path, description in integration_tests:
            cmd = ["python", "-m", "pytest", f"agents/triage/tests/{test_path}", "-v", "--tb=short", "-m", "not slow"]
            if not self.run_command(cmd, description):
                success = False
        
        return success
    
    def run_comparison_tests(self):
        """Run comparison tests between v6 and v7."""
        print("\n⚖️  Running Comparison Tests")
        
        cmd = ["python", "-m", "pytest", "agents/triage/tests/test_classifier_comparison.py", "-v", "--tb=short"]
        return self.run_command(cmd, "Classifier Comparison Tests")
    
    def run_performance_tests(self):
        """Run performance tests if requested."""
        print("\n🚀 Running Performance Tests")
        
        # Set environment to enable performance tests
        env = os.environ.copy()
        env['RUN_COMPARISON_TESTS'] = '1'
        
        cmd = ["python", "-m", "pytest", "agents/triage/tests/test_classifier_comparison.py::TestClassifierIntegrationComparison::test_side_by_side_comparison", "-v", "-s"]
        
        try:
            result = subprocess.run(cmd, env=env, cwd=self.project_root, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"Error running performance tests: {e}")
            return False
    
    def run_configuration_tests(self):
        """Run configuration validation tests."""
        print("\n⚙️  Running Configuration Tests")
        
        config_tests = [
            ("test_classifier_v6_comprehensive.py::TestClassifierV6Configuration", "V6 Config"),
            ("test_classifier_v7_comprehensive.py::TestClassifierV7Configuration", "V7 Config"),
            ("test_classifier_v7_comprehensive.py::TestClassifierV7DeviceUtils", "V7 Device Utils")
        ]
        
        success = True
        for test_path, description in config_tests:
            cmd = ["python", "-m", "pytest", f"agents/triage/tests/{test_path}", "-v"]
            if not self.run_command(cmd, description):
                success = False
        
        return success
    
    def generate_test_report(self):
        """Generate a comprehensive test report."""
        print("\n📊 Generating Test Report")
        
        report_cmd = [
            "python", "-m", "pytest",
            "agents/triage/tests/test_classifier_v6_comprehensive.py",
            "agents/triage/tests/test_classifier_v7_comprehensive.py", 
            "agents/triage/tests/test_classifier_comparison.py",
            "--tb=short",
            "-v",
            "--html=test_report.html",
            "--self-contained-html"
        ]
        
        if self.run_command(report_cmd, "Generating HTML test report"):
            print("📋 Test report generated: test_report.html")
            return True
        else:
            print("⚠️  Test report generation failed")
            return False


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description="Run classifier tests")
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--comparison', action='store_true', help='Run comparison tests only')
    parser.add_argument('--performance', action='store_true', help='Run performance tests')
    parser.add_argument('--config', action='store_true', help='Run configuration tests only')
    parser.add_argument('--report', action='store_true', help='Generate HTML report')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--check-deps', action='store_true', help='Check dependencies only')
    
    args = parser.parse_args()
    
    runner = ClassifierTestRunner()
    
    # Check dependencies first
    if not runner.check_dependencies():
        if args.check_deps:
            return 1
        print("❌ Missing dependencies. Install them before running tests.")
        return 1
    
    if args.check_deps:
        print("✅ All dependencies available")
        return 0
    
    success = True
    
    if args.unit or args.all:
        if not runner.run_unit_tests():
            success = False
    
    if args.config or args.all:
        if not runner.run_configuration_tests():
            success = False
    
    if args.integration or args.all:
        if not runner.run_integration_tests():
            success = False
    
    if args.comparison or args.all:
        if not runner.run_comparison_tests():
            success = False
    
    if args.performance:
        if not runner.run_performance_tests():
            success = False
    
    if args.report:
        runner.generate_test_report()
    
    if not any([args.unit, args.integration, args.comparison, args.performance, 
                args.config, args.report, args.all, args.check_deps]):
        print("No test type specified. Use --help for options.")
        print("\nQuick start:")
        print("  python run_classifier_tests.py --unit       # Run unit tests")
        print("  python run_classifier_tests.py --all        # Run all tests")
        print("  python run_classifier_tests.py --check-deps # Check dependencies")
        return 1
    
    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())