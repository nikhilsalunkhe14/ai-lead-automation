#!/usr/bin/env python3
"""
AI Lead Automation - Health Check Script
Tests all system components and generates a comprehensive health report
"""

import requests
import json
from datetime import datetime
import sys

class HealthChecker:
    def __init__(self, base_url='http://127.0.0.1:5000'):
        self.base_url = base_url
        self.results = {}
        
    def test_endpoint(self, endpoint, method='GET', data=None, expected_status=200):
        """Test a specific endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method == 'GET':
                response = requests.get(url, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=10)
            else:
                return False, f"Unsupported method: {method}"
            
            status_ok = response.status_code == expected_status
            
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            return status_ok, {
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'data': response_data
            }
            
        except requests.exceptions.RequestException as e:
            return False, f"Request failed: {str(e)}"
    
    def check_database_status(self):
        """Check database connection"""
        success, result = self.test_endpoint('/api/db-status')
        self.results['database'] = {
            'status': '✅ Connected' if success else '❌ Disconnected',
            'details': result if success else str(result)
        }
        return success
    
    def check_main_pages(self):
        """Check all main page routes"""
        pages = [
            ('/', 'Welcome Page'),
            ('/dashboard', 'Dashboard'),
            ('/admin_login', 'Admin Login'),
            ('/admin_dashboard', 'Admin Dashboard'),
            ('/admin_register', 'Admin Registration'),
            ('/memory_dashboard', 'Memory Dashboard'),
            ('/context_dashboard', 'Context Dashboard'),
            ('/analytics_dashboard', 'Analytics Dashboard'),
            ('/landing', 'Landing Page')
        ]
        
        page_results = {}
        for endpoint, name in pages:
            success, result = self.test_endpoint(endpoint)
            page_results[name] = {
                'status': '✅ Working' if success else '❌ Failed',
                'url': endpoint,
                'response_time': result.get('response_time', 0) if success else 0
            }
        
        self.results['pages'] = page_results
        return all('✅' in result['status'] for result in page_results.values())
    
    def check_api_endpoints(self):
        """Check all API endpoints"""
        apis = [
            ('/api/test', 'API Test'),
            ('/api/memory/stats', 'Memory Stats'),
            ('/api/context/stats', 'Context Stats'),
            ('/api/analytics/stats', 'Analytics Stats'),
            ('/api/analytics/stats?period=week', 'Analytics (Week)'),
            ('/api/context/search?q=test', 'Context Search')
        ]
        
        api_results = {}
        for endpoint, name in apis:
            success, result = self.test_endpoint(endpoint)
            api_results[name] = {
                'status': '✅ Working' if success else '❌ Failed',
                'endpoint': endpoint,
                'response_time': result.get('response_time', 0) if success else 0
            }
        
        self.results['apis'] = api_results
        return all('✅' in result['status'] for result in api_results.values())
    
    def check_static_assets(self):
        """Check static asset accessibility"""
        assets = [
            ('/static/css/style.css', 'Main CSS'),
            ('/static/js/main.js', 'Main JS')
        ]
        
        asset_results = {}
        for asset, name in assets:
            success, result = self.test_endpoint(asset)
            asset_results[name] = {
                'status': '✅ Available' if success else '❌ Missing',
                'path': asset,
                'size': len(result.get('data', '')) if success else 0
            }
        
        self.results['static_assets'] = asset_results
        return all('✅' in result['status'] for result in asset_results.values())
    
    def run_full_check(self):
        """Run comprehensive health check"""
        print("=" * 80)
        print("🔍 AI Lead Automation - System Health Check")
        print("=" * 80)
        print(f"📅 Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Target URL: {self.base_url}")
        print("=" * 80)
        
        # Run all checks
        db_ok = self.check_database_status()
        pages_ok = self.check_main_pages()
        apis_ok = self.check_api_endpoints()
        assets_ok = self.check_static_assets()
        
        # Generate report
        print("\n📊 SYSTEM STATUS REPORT")
        print("=" * 80)
        
        # Database Status
        print(f"\n🗄️  DATABASE STATUS")
        print(f"   {self.results['database']['status']}")
        if 'details' in self.results['database']:
            print(f"   Details: {self.results['database']['details']}")
        
        # Pages Status
        print(f"\n📄 PAGE ROUTES")
        for name, result in self.results['pages'].items():
            status = result['status']
            time_ms = f"({result['response_time']*1000:.0f}ms)" if result['response_time'] > 0 else ""
            print(f"   {status} {name} {time_ms}")
        
        # API Status
        print(f"\n🔌 API ENDPOINTS")
        for name, result in self.results['apis'].items():
            status = result['status']
            time_ms = f"({result['response_time']*1000:.0f}ms)" if result['response_time'] > 0 else ""
            print(f"   {status} {name} {time_ms}")
        
        # Static Assets
        print(f"\n🎨 STATIC ASSETS")
        for name, result in self.results['static_assets'].items():
            status = result['status']
            size_kb = f"({result['size']/1024:.1f}KB)" if result['size'] > 0 else ""
            print(f"   {status} {name} {size_kb}")
        
        # Overall Status
        print(f"\n🎯 OVERALL STATUS")
        all_ok = db_ok and pages_ok and apis_ok and assets_ok
        
        if all_ok:
            print("   ✅ ALL SYSTEMS OPERATIONAL")
            print("   🚀 Application is fully functional")
        else:
            print("   ⚠️  SOME ISSUES DETECTED")
            print("   🔧 Review the report above for details")
        
        # Summary Statistics
        total_pages = len(self.results['pages'])
        working_pages = sum(1 for r in self.results['pages'].values() if '✅' in r['status'])
        
        total_apis = len(self.results['apis'])
        working_apis = sum(1 for r in self.results['apis'].values() if '✅' in r['status'])
        
        total_assets = len(self.results['static_assets'])
        working_assets = sum(1 for r in self.results['static_assets'].values() if '✅' in r['status'])
        
        print(f"\n📈 SUMMARY STATISTICS")
        print(f"   Pages: {working_pages}/{total_pages} working")
        print(f"   APIs: {working_apis}/{total_apis} working")
        print(f"   Assets: {working_assets}/{total_assets} available")
        print(f"   Database: {'Connected' if db_ok else 'Disconnected'}")
        
        print("=" * 80)
        
        return all_ok

if __name__ == '__main__':
    checker = HealthChecker()
    success = checker.run_full_check()
    
    if success:
        print("\n🎉 Health check completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Health check found issues. Please review the report.")
        sys.exit(1)
