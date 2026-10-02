#!/usr/bin/env python3
"""
Backend API Test Suite for NEW OptimoRoute Features
Tests: Late Flag, Proof of Delivery, Import with Geocoding
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any

# Backend URL from frontend/.env
BASE_URL = "https://route-optimizer-464.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log_test(name: str):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

def log_pass(msg: str):
    print(f"{Colors.GREEN}✓ PASS: {msg}{Colors.END}")

def log_fail(msg: str):
    print(f"{Colors.RED}✗ FAIL: {msg}{Colors.END}")

def log_info(msg: str):
    print(f"{Colors.YELLOW}ℹ INFO: {msg}{Colors.END}")

# Global variables to store test data
test_data = {
    "today": datetime.utcnow().strftime("%Y-%m-%d"),
    "scheduled_order_id": None,
    "scheduled_order_id_2": None,
}

def test_1_setup_seed_and_optimize():
    """Test 1: Setup - POST /api/seed then POST /api/optimize"""
    log_test("1. SETUP - Seed data and optimize routes")
    
    try:
        # Seed
        log_info("Seeding data...")
        response = requests.post(f"{BASE_URL}/seed", timeout=10)
        
        if response.status_code != 200:
            log_fail(f"Seed failed: status {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        data = response.json()
        log_pass(f"Seed successful: {data}")
        
        # Optimize
        log_info("Optimizing routes...")
        payload = {"date": test_data["today"]}
        response = requests.post(f"{BASE_URL}/optimize", json=payload, timeout=30)
        
        if response.status_code != 200:
            log_fail(f"Optimize failed: status {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        data = response.json()
        log_pass(f"Optimize successful: assigned={data['assigned']}, unassigned={data['unassigned']}, drivers_used={data['drivers_used']}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def test_2_late_flag():
    """Test 2: LATE FLAG - Verify orders have 'late' field after optimization"""
    log_test("2. LATE FLAG - Verify late field on orders")
    
    try:
        # GET orders
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        
        if response.status_code != 200:
            log_fail(f"GET orders failed: status {response.status_code}")
            return False
        
        orders = response.json()
        log_info(f"Found {len(orders)} orders")
        
        if len(orders) == 0:
            log_fail("No orders found")
            return False
        
        # Check that 'late' field exists on all orders
        missing_late = []
        late_orders = []
        on_time_orders = []
        
        for order in orders:
            if "late" not in order:
                missing_late.append(order.get("order_no", order.get("id")))
            else:
                if order["late"]:
                    late_orders.append(order)
                else:
                    on_time_orders.append(order)
        
        if missing_late:
            log_fail(f"{len(missing_late)} orders missing 'late' field: {missing_late[:5]}")
            return False
        
        log_pass(f"All {len(orders)} orders have 'late' field")
        
        # Verify late orders have eta > tw_end
        log_info(f"Late orders: {len(late_orders)}, On-time orders: {len(on_time_orders)}")
        
        if len(late_orders) == 0:
            log_info("WARNING: No late orders found. Expected some distant pharmacies (Rambouillet/Mennecy/Corbeil/Le Mée) with tw_end 09:30 to be late.")
        
        # Check a few late orders
        for order in late_orders[:5]:
            eta = order.get("eta", "")
            tw_end = order.get("tw_end", "")
            customer = order.get("customer", "")
            log_info(f"Late order: {customer} - ETA: {eta}, TW_END: {tw_end}")
            
            # Verify eta > tw_end
            if eta and tw_end:
                eta_minutes = int(eta.split(":")[0]) * 60 + int(eta.split(":")[1])
                tw_end_minutes = int(tw_end.split(":")[0]) * 60 + int(tw_end.split(":")[1])
                
                if eta_minutes <= tw_end_minutes:
                    log_fail(f"Order {order.get('order_no')} marked late but eta ({eta}) <= tw_end ({tw_end})")
                    return False
        
        # Check a few on-time orders
        for order in on_time_orders[:5]:
            eta = order.get("eta", "")
            tw_end = order.get("tw_end", "")
            customer = order.get("customer", "")
            
            # Verify eta <= tw_end
            if eta and tw_end:
                eta_minutes = int(eta.split(":")[0]) * 60 + int(eta.split(":")[1])
                tw_end_minutes = int(tw_end.split(":")[0]) * 60 + int(tw_end.split(":")[1])
                
                if eta_minutes > tw_end_minutes:
                    log_fail(f"Order {order.get('order_no')} marked on-time but eta ({eta}) > tw_end ({tw_end})")
                    return False
        
        log_pass(f"Late flag verified: {len(late_orders)} late orders, {len(on_time_orders)} on-time orders")
        
        # Store a scheduled order ID for POD test
        scheduled = [o for o in orders if o["status"] == "scheduled"]
        if scheduled:
            test_data["scheduled_order_id"] = scheduled[0]["id"]
            if len(scheduled) > 1:
                test_data["scheduled_order_id_2"] = scheduled[1]["id"]
            log_info(f"Stored scheduled order IDs for POD test: {test_data['scheduled_order_id'][:8]}...")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def test_3_proof_of_delivery_success():
    """Test 3: PROOF OF DELIVERY - Complete order with success=true"""
    log_test("3. PROOF OF DELIVERY - Complete order successfully")
    
    try:
        if not test_data["scheduled_order_id"]:
            log_fail("No scheduled order ID available for POD test")
            return False
        
        order_id = test_data["scheduled_order_id"]
        
        # Complete order with success=true
        log_info(f"Completing order {order_id[:8]}... with success=true")
        payload = {
            "success": True,
            "signature": "data:image/png;base64,iVBORw0KGgo=",
            "photo": "data:image/png;base64,iVBORw0KGgo=",
            "note": "remis au pharmacien"
        }
        response = requests.post(f"{BASE_URL}/orders/{order_id}/complete", json=payload, timeout=10)
        
        if response.status_code != 200:
            log_fail(f"Complete order failed: status {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        completed_order = response.json()
        log_info(f"Response: {json.dumps(completed_order, indent=2)}")
        
        # Verify status is "completed"
        if completed_order.get("status") != "completed":
            log_fail(f"Expected status='completed', got '{completed_order.get('status')}'")
            return False
        
        log_pass("Status changed to 'completed'")
        
        # Verify signature persisted
        if completed_order.get("signature") != payload["signature"]:
            log_fail(f"Signature not persisted correctly")
            return False
        
        log_pass("Signature persisted")
        
        # Verify photo persisted
        if completed_order.get("photo") != payload["photo"]:
            log_fail(f"Photo not persisted correctly")
            return False
        
        log_pass("Photo persisted")
        
        # Verify pod_note persisted
        if completed_order.get("pod_note") != payload["note"]:
            log_fail(f"POD note not persisted correctly")
            return False
        
        log_pass("POD note persisted")
        
        # Verify completed_at is set
        if not completed_order.get("completed_at"):
            log_fail("completed_at not set")
            return False
        
        log_pass(f"completed_at set: {completed_order['completed_at']}")
        
        # GET order again to verify persistence
        log_info("Fetching order again to verify persistence...")
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        orders = response.json()
        fetched_order = [o for o in orders if o["id"] == order_id]
        
        if not fetched_order:
            log_fail("Completed order not found in GET /api/orders")
            return False
        
        fetched_order = fetched_order[0]
        
        # Verify all fields persisted
        if fetched_order.get("status") != "completed":
            log_fail(f"GET: status not persisted, got '{fetched_order.get('status')}'")
            return False
        
        if fetched_order.get("signature") != payload["signature"]:
            log_fail("GET: signature not persisted")
            return False
        
        if fetched_order.get("photo") != payload["photo"]:
            log_fail("GET: photo not persisted")
            return False
        
        if fetched_order.get("pod_note") != payload["note"]:
            log_fail("GET: pod_note not persisted")
            return False
        
        if not fetched_order.get("completed_at"):
            log_fail("GET: completed_at not persisted")
            return False
        
        log_pass("All POD fields persisted correctly (verified via GET)")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def test_4_proof_of_delivery_failed():
    """Test 4: PROOF OF DELIVERY - Complete order with success=false"""
    log_test("4. PROOF OF DELIVERY - Failed delivery")
    
    try:
        if not test_data["scheduled_order_id_2"]:
            log_fail("No second scheduled order ID available for failed POD test")
            return False
        
        order_id = test_data["scheduled_order_id_2"]
        
        # Complete order with success=false
        log_info(f"Completing order {order_id[:8]}... with success=false")
        payload = {
            "success": False,
            "note": "absent"
        }
        response = requests.post(f"{BASE_URL}/orders/{order_id}/complete", json=payload, timeout=10)
        
        if response.status_code != 200:
            log_fail(f"Complete order failed: status {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        failed_order = response.json()
        log_info(f"Response: {json.dumps(failed_order, indent=2)}")
        
        # Verify status is "failed"
        if failed_order.get("status") != "failed":
            log_fail(f"Expected status='failed', got '{failed_order.get('status')}'")
            return False
        
        log_pass("Status changed to 'failed'")
        
        # Verify pod_note persisted
        if failed_order.get("pod_note") != payload["note"]:
            log_fail(f"POD note not persisted correctly")
            return False
        
        log_pass("POD note persisted")
        
        # Verify completed_at is set
        if not failed_order.get("completed_at"):
            log_fail("completed_at not set")
            return False
        
        log_pass(f"completed_at set: {failed_order['completed_at']}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def test_5_import_with_geocoding():
    """Test 5: IMPORT - Import orders with geocoding"""
    log_test("5. IMPORT - Import orders with geocoding")
    
    try:
        # Import 2 orders
        log_info("Importing 2 orders (Versailles, Aulnay-sous-Bois)...")
        payload = {
            "date": test_data["today"],
            "rows": [
                {
                    "customer": "Pharmacie Import A",
                    "address": "Versailles (78)",
                    "amount": 120,
                    "load": 2,
                    "order_no": "PL900001"
                },
                {
                    "customer": "Pharmacie Import B",
                    "address": "Aulnay-sous-Bois (93)",
                    "amount": 0,
                    "load": 1
                }
            ]
        }
        response = requests.post(f"{BASE_URL}/orders/import", json=payload, timeout=10)
        
        if response.status_code != 200:
            log_fail(f"Import failed: status {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        result = response.json()
        log_info(f"Response: {json.dumps(result, indent=2)}")
        
        # Verify response
        if result.get("created") != 2:
            log_fail(f"Expected created=2, got {result.get('created')}")
            return False
        
        log_pass("Created 2 orders")
        
        if result.get("geocoded") != 2:
            log_fail(f"Expected geocoded=2, got {result.get('geocoded')}")
            return False
        
        log_pass("Geocoded 2 orders")
        
        # GET orders to verify they exist
        log_info("Fetching orders to verify import...")
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        orders = response.json()
        
        # Find imported orders
        import_a = [o for o in orders if o.get("customer") == "Pharmacie Import A"]
        import_b = [o for o in orders if o.get("customer") == "Pharmacie Import B"]
        
        if not import_a:
            log_fail("Pharmacie Import A not found")
            return False
        
        if not import_b:
            log_fail("Pharmacie Import B not found")
            return False
        
        log_pass("Both imported orders found")
        
        # Verify Import A
        order_a = import_a[0]
        log_info(f"Import A: {order_a['customer']} - {order_a['address']} - lat: {order_a['lat']}, lng: {order_a['lng']}, amount: {order_a['amount']}, order_no: {order_a['order_no']}")
        
        if order_a.get("status") != "unscheduled":
            log_fail(f"Import A: Expected status='unscheduled', got '{order_a.get('status')}'")
            return False
        
        if order_a.get("amount") != 120:
            log_fail(f"Import A: Expected amount=120, got {order_a.get('amount')}")
            return False
        
        if order_a.get("order_no") != "PL900001":
            log_fail(f"Import A: Expected order_no='PL900001', got '{order_a.get('order_no')}'")
            return False
        
        # Verify geocoding - lat/lng should be within Île-de-France bounds
        lat_a = order_a.get("lat")
        lng_a = order_a.get("lng")
        
        if lat_a is None or lng_a is None:
            log_fail(f"Import A: lat/lng is None")
            return False
        
        if not (48.0 <= lat_a <= 49.2):
            log_fail(f"Import A: lat {lat_a} out of Île-de-France bounds (48-49.2)")
            return False
        
        if not (1.4 <= lng_a <= 3.2):
            log_fail(f"Import A: lng {lng_a} out of Île-de-France bounds (1.4-3.2)")
            return False
        
        log_pass(f"Import A geocoded correctly: lat={lat_a:.4f}, lng={lng_a:.4f} (within Île-de-France)")
        
        # Verify Import B
        order_b = import_b[0]
        log_info(f"Import B: {order_b['customer']} - {order_b['address']} - lat: {order_b['lat']}, lng: {order_b['lng']}, amount: {order_b['amount']}, order_no: {order_b['order_no']}")
        
        if order_b.get("status") != "unscheduled":
            log_fail(f"Import B: Expected status='unscheduled', got '{order_b.get('status')}'")
            return False
        
        if order_b.get("amount") != 0:
            log_fail(f"Import B: Expected amount=0, got {order_b.get('amount')}")
            return False
        
        # Verify order_no was auto-generated (not empty)
        if not order_b.get("order_no"):
            log_fail(f"Import B: order_no not auto-generated")
            return False
        
        log_pass(f"Import B order_no auto-generated: {order_b['order_no']}")
        
        # Verify geocoding
        lat_b = order_b.get("lat")
        lng_b = order_b.get("lng")
        
        if lat_b is None or lng_b is None:
            log_fail(f"Import B: lat/lng is None")
            return False
        
        if not (48.0 <= lat_b <= 49.2):
            log_fail(f"Import B: lat {lat_b} out of Île-de-France bounds (48-49.2)")
            return False
        
        if not (1.4 <= lng_b <= 3.2):
            log_fail(f"Import B: lng {lng_b} out of Île-de-France bounds (1.4-3.2)")
            return False
        
        log_pass(f"Import B geocoded correctly: lat={lat_b:.4f}, lng={lng_b:.4f} (within Île-de-France)")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def test_6_import_with_explicit_coords():
    """Test 6: IMPORT - Import order with explicit lat/lng (should NOT geocode)"""
    log_test("6. IMPORT - Import with explicit lat/lng (no geocoding)")
    
    try:
        # Import 1 order with explicit lat/lng
        log_info("Importing 1 order with explicit lat=48.85, lng=2.35...")
        payload = {
            "date": test_data["today"],
            "rows": [
                {
                    "customer": "Pharmacie Import C",
                    "address": "Paris (75)",
                    "amount": 50,
                    "load": 1,
                    "lat": 48.85,
                    "lng": 2.35
                }
            ]
        }
        response = requests.post(f"{BASE_URL}/orders/import", json=payload, timeout=10)
        
        if response.status_code != 200:
            log_fail(f"Import failed: status {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        result = response.json()
        log_info(f"Response: {json.dumps(result, indent=2)}")
        
        # Verify response
        if result.get("created") != 1:
            log_fail(f"Expected created=1, got {result.get('created')}")
            return False
        
        log_pass("Created 1 order")
        
        # Verify geocoded=0 (should NOT geocode when lat/lng provided)
        if result.get("geocoded") != 0:
            log_fail(f"Expected geocoded=0 (no geocoding when lat/lng provided), got {result.get('geocoded')}")
            return False
        
        log_pass("Geocoded=0 (correct, lat/lng was provided)")
        
        # GET orders to verify coordinates
        log_info("Fetching orders to verify coordinates...")
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        orders = response.json()
        
        # Find imported order
        import_c = [o for o in orders if o.get("customer") == "Pharmacie Import C"]
        
        if not import_c:
            log_fail("Pharmacie Import C not found")
            return False
        
        order_c = import_c[0]
        log_info(f"Import C: {order_c['customer']} - lat: {order_c['lat']}, lng: {order_c['lng']}")
        
        # Verify exact coordinates
        if order_c.get("lat") != 48.85:
            log_fail(f"Import C: Expected lat=48.85, got {order_c.get('lat')}")
            return False
        
        if order_c.get("lng") != 2.35:
            log_fail(f"Import C: Expected lng=2.35, got {order_c.get('lng')}")
            return False
        
        log_pass(f"Import C kept exact coordinates: lat=48.85, lng=2.35 (not geocoded)")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def main():
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}OptimoRoute NEW Features - Backend Test Suite{Colors.END}")
    print(f"{Colors.BLUE}Base URL: {BASE_URL}{Colors.END}")
    print(f"{Colors.BLUE}Test Date: {test_data['today']}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")
    
    tests = [
        ("Setup: Seed and Optimize", test_1_setup_seed_and_optimize),
        ("Late Flag: Verify late field on orders", test_2_late_flag),
        ("POD: Complete order successfully", test_3_proof_of_delivery_success),
        ("POD: Failed delivery", test_4_proof_of_delivery_failed),
        ("Import: Geocoding for 2 orders", test_5_import_with_geocoding),
        ("Import: Explicit lat/lng (no geocoding)", test_6_import_with_explicit_coords),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            log_fail(f"Test '{name}' crashed: {str(e)}")
            results.append((name, False))
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if result else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"{status}: {name}")
    
    print(f"\n{Colors.BLUE}Total: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}ALL TESTS PASSED!{Colors.END}")
        print(f"{Colors.GREEN}{'='*80}{Colors.END}")
        return 0
    else:
        print(f"{Colors.RED}{'='*80}{Colors.END}")
        print(f"{Colors.RED}SOME TESTS FAILED{Colors.END}")
        print(f"{Colors.RED}{'='*80}{Colors.END}")
        return 1

if __name__ == "__main__":
    exit(main())
