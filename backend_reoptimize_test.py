#!/usr/bin/env python3
"""
Backend API Test Suite for Reoptimization Features
Tests POST /api/routes/reoptimize and POST /api/orders/assign recomputation
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
    "drivers": [],
    "orders": [],
}

def setup_data():
    """Setup: POST /api/seed then POST /api/optimize"""
    log_test("SETUP: Seed data and optimize routes")
    
    try:
        # Seed data
        log_info("Seeding data...")
        response = requests.post(f"{BASE_URL}/seed", timeout=10)
        if response.status_code != 200:
            log_fail(f"Seed failed: {response.status_code}")
            return False
        
        seed_data = response.json()
        log_pass(f"Seed successful: {seed_data}")
        
        # Optimize routes
        log_info("Optimizing routes...")
        payload = {"date": test_data["today"]}
        response = requests.post(f"{BASE_URL}/optimize", json=payload, timeout=30)
        if response.status_code != 200:
            log_fail(f"Optimize failed: {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        optimize_data = response.json()
        log_pass(f"Optimize successful: {optimize_data}")
        
        # Get drivers
        response = requests.get(f"{BASE_URL}/drivers", timeout=10)
        if response.status_code != 200:
            log_fail(f"Get drivers failed: {response.status_code}")
            return False
        test_data["drivers"] = response.json()
        log_info(f"Found {len(test_data['drivers'])} drivers")
        
        # Get orders
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get orders failed: {response.status_code}")
            return False
        test_data["orders"] = response.json()
        log_info(f"Found {len(test_data['orders'])} orders")
        
        return True
        
    except Exception as e:
        log_fail(f"Setup exception: {str(e)}")
        return False


def test_1_reoptimize_all():
    """Test 1: POST /api/routes/reoptimize {"date":"<today>"} -> expect {reoptimized:6, late_before:<n>, late_after:<n>}"""
    log_test("1. REOPTIMIZE ALL - POST /api/routes/reoptimize with date only")
    
    try:
        payload = {"date": test_data["today"]}
        response = requests.post(f"{BASE_URL}/routes/reoptimize", json=payload, timeout=30)
        
        if response.status_code != 200:
            log_fail(f"Expected status 200, got {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        data = response.json()
        log_info(f"Response: {json.dumps(data, indent=2)}")
        
        # Verify response structure
        required_fields = ["reoptimized", "late_before", "late_after"]
        for field in required_fields:
            if field not in data:
                log_fail(f"Missing field: {field}")
                return False
        
        reoptimized = data["reoptimized"]
        late_before = data["late_before"]
        late_after = data["late_after"]
        
        # Expect reoptimized to be 6 (all drivers)
        if reoptimized != 6:
            log_fail(f"Expected reoptimized=6, got {reoptimized}")
            return False
        
        log_pass(f"Reoptimized all {reoptimized} drivers: late_before={late_before}, late_after={late_after}")
        
        # Verify all orders still have sequence and eta
        log_info("Verifying all orders still have sequence and eta...")
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get orders failed: {response.status_code}")
            return False
        
        orders = response.json()
        scheduled = [o for o in orders if o["status"] == "scheduled"]
        
        errors = []
        for order in scheduled:
            if order.get("sequence") is None:
                errors.append(f"Order {order['order_no']}: missing sequence after reoptimize")
            if not order.get("eta"):
                errors.append(f"Order {order['order_no']}: missing eta after reoptimize")
        
        if errors:
            for err in errors[:5]:
                log_fail(err)
            return False
        
        log_pass(f"All {len(scheduled)} scheduled orders still have sequence and eta after reoptimize")
        
        # Verify sequences are contiguous per driver
        driver_sequences = {}
        for order in scheduled:
            driver_id = order["assigned_driver_id"]
            seq = order["sequence"]
            if driver_id not in driver_sequences:
                driver_sequences[driver_id] = []
            driver_sequences[driver_id].append(seq)
        
        for driver_id, sequences in driver_sequences.items():
            sequences.sort()
            expected = list(range(1, len(sequences) + 1))
            if sequences != expected:
                log_fail(f"Driver {driver_id}: sequences {sequences} not contiguous from 1")
                return False
        
        log_pass("All driver sequences are contiguous starting at 1")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def test_2_reoptimize_one_driver():
    """Test 2: POST /api/routes/reoptimize {"date":"<today>","driver_id":"<id>"} -> expect reoptimized:1"""
    log_test("2. REOPTIMIZE ONE DRIVER - POST /api/routes/reoptimize with driver_id")
    
    try:
        # Get routes to find a driver with orders
        response = requests.get(f"{BASE_URL}/routes", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get routes failed: {response.status_code}")
            return False
        
        routes_data = response.json()
        routes = routes_data.get("routes", [])
        
        if not routes:
            log_fail("No routes found")
            return False
        
        # Pick first driver with a route
        driver_id = routes[0]["driver"]["id"]
        driver_name = routes[0]["driver"]["name"]
        log_info(f"Testing reoptimize for driver: {driver_name} (id: {driver_id[:8]}...)")
        
        # Get driver's orders before reoptimize
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get orders failed: {response.status_code}")
            return False
        
        orders = response.json()
        driver_orders_before = [o for o in orders if o.get("assigned_driver_id") == driver_id and o["status"] == "scheduled"]
        log_info(f"Driver has {len(driver_orders_before)} orders before reoptimize")
        
        # Reoptimize this driver only
        payload = {"date": test_data["today"], "driver_id": driver_id}
        response = requests.post(f"{BASE_URL}/routes/reoptimize", json=payload, timeout=30)
        
        if response.status_code != 200:
            log_fail(f"Expected status 200, got {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        data = response.json()
        log_info(f"Response: {json.dumps(data, indent=2)}")
        
        # Verify response structure
        if "reoptimized" not in data:
            log_fail("Missing 'reoptimized' field")
            return False
        
        reoptimized = data["reoptimized"]
        
        # Expect reoptimized=1 (only one driver)
        if reoptimized != 1:
            log_fail(f"Expected reoptimized=1, got {reoptimized}")
            return False
        
        log_pass(f"Reoptimized 1 driver: {driver_name}")
        
        # Verify driver's orders still have sequence and eta
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get orders failed: {response.status_code}")
            return False
        
        orders = response.json()
        driver_orders_after = [o for o in orders if o.get("assigned_driver_id") == driver_id and o["status"] == "scheduled"]
        
        if len(driver_orders_after) != len(driver_orders_before):
            log_fail(f"Driver order count changed: before={len(driver_orders_before)}, after={len(driver_orders_after)}")
            return False
        
        errors = []
        for order in driver_orders_after:
            if order.get("sequence") is None:
                errors.append(f"Order {order['order_no']}: missing sequence")
            if not order.get("eta"):
                errors.append(f"Order {order['order_no']}: missing eta")
        
        if errors:
            for err in errors:
                log_fail(err)
            return False
        
        # Verify sequences are contiguous starting at 1
        sequences = sorted([o["sequence"] for o in driver_orders_after])
        expected = list(range(1, len(sequences) + 1))
        if sequences != expected:
            log_fail(f"Sequences {sequences} not contiguous from 1")
            return False
        
        log_pass(f"Driver {driver_name} has {len(driver_orders_after)} orders with contiguous sequences 1-{len(sequences)} and valid eta")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def test_3_assign_recomputes_both_source_and_target():
    """Test 3: ASSIGN RECOMPUTES BOTH SOURCE & TARGET - drag simulation"""
    log_test("3. ASSIGN RECOMPUTES BOTH SOURCE & TARGET - Move order from driver A to driver B")
    
    try:
        # Get routes to find drivers with orders
        response = requests.get(f"{BASE_URL}/routes", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get routes failed: {response.status_code}")
            return False
        
        routes_data = response.json()
        routes = routes_data.get("routes", [])
        
        if len(routes) < 2:
            log_fail(f"Need at least 2 routes, found {len(routes)}")
            return False
        
        # Find driver A with >= 2 stops
        driver_a = None
        driver_a_route = None
        for route in routes:
            if route["total_stops"] >= 2:
                driver_a = route["driver"]
                driver_a_route = route
                break
        
        if not driver_a:
            log_fail("Could not find driver with >= 2 stops")
            return False
        
        # Find a different driver B
        driver_b = None
        for route in routes:
            if route["driver"]["id"] != driver_a["id"]:
                driver_b = route["driver"]
                break
        
        if not driver_b:
            log_fail("Could not find second driver")
            return False
        
        log_info(f"Driver A: {driver_a['name']} (id: {driver_a['id'][:8]}...) with {driver_a_route['total_stops']} stops")
        log_info(f"Driver B: {driver_b['name']} (id: {driver_b['id'][:8]}...)")
        
        # Get orders for driver A
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get orders failed: {response.status_code}")
            return False
        
        orders = response.json()
        driver_a_orders = [o for o in orders if o.get("assigned_driver_id") == driver_a["id"] and o["status"] == "scheduled"]
        driver_b_orders_before = [o for o in orders if o.get("assigned_driver_id") == driver_b["id"] and o["status"] == "scheduled"]
        
        if len(driver_a_orders) < 2:
            log_fail(f"Driver A has only {len(driver_a_orders)} orders, need >= 2")
            return False
        
        # Pick one order from driver A to move
        order_to_move = driver_a_orders[0]
        log_info(f"Moving order: {order_to_move['order_no']} (id: {order_to_move['id'][:8]}...) from {driver_a['name']} to {driver_b['name']}")
        log_info(f"Driver A orders before: {len(driver_a_orders)}, Driver B orders before: {len(driver_b_orders_before)}")
        
        # Store driver A's remaining order IDs
        driver_a_remaining_ids = [o["id"] for o in driver_a_orders if o["id"] != order_to_move["id"]]
        
        # Assign order to driver B
        payload = {"order_id": order_to_move["id"], "driver_id": driver_b["id"]}
        response = requests.post(f"{BASE_URL}/orders/assign", json=payload, timeout=10)
        
        if response.status_code != 200:
            log_fail(f"Assign failed: {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        assigned_order = response.json()
        log_info(f"Assign response: order_no={assigned_order['order_no']}, assigned_driver_id={assigned_order.get('assigned_driver_id', 'N/A')[:8] if assigned_order.get('assigned_driver_id') else 'None'}..., status={assigned_order['status']}, sequence={assigned_order.get('sequence')}, eta={assigned_order.get('eta')}")
        
        # Verify moved order now has driver B
        if assigned_order.get("assigned_driver_id") != driver_b["id"]:
            log_fail(f"Order assigned_driver_id={assigned_order.get('assigned_driver_id')}, expected {driver_b['id']}")
            return False
        
        if assigned_order["status"] != "scheduled":
            log_fail(f"Order status={assigned_order['status']}, expected 'scheduled'")
            return False
        
        if assigned_order.get("sequence") is None:
            log_fail("Order missing sequence after assign")
            return False
        
        if not assigned_order.get("eta"):
            log_fail("Order missing eta after assign")
            return False
        
        log_pass(f"Moved order now assigned to {driver_b['name']} with sequence={assigned_order['sequence']}, eta={assigned_order['eta']}")
        
        # Get all orders again to verify recomputation
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get orders failed: {response.status_code}")
            return False
        
        orders = response.json()
        driver_a_orders_after = [o for o in orders if o.get("assigned_driver_id") == driver_a["id"] and o["status"] == "scheduled"]
        driver_b_orders_after = [o for o in orders if o.get("assigned_driver_id") == driver_b["id"] and o["status"] == "scheduled"]
        
        log_info(f"Driver A orders after: {len(driver_a_orders_after)}, Driver B orders after: {len(driver_b_orders_after)}")
        
        # Verify driver A has one less order
        if len(driver_a_orders_after) != len(driver_a_orders) - 1:
            log_fail(f"Driver A should have {len(driver_a_orders) - 1} orders, has {len(driver_a_orders_after)}")
            return False
        
        # Verify driver B has one more order
        if len(driver_b_orders_after) != len(driver_b_orders_before) + 1:
            log_fail(f"Driver B should have {len(driver_b_orders_before) + 1} orders, has {len(driver_b_orders_after)}")
            return False
        
        # Verify driver A's remaining orders were re-sequenced (contiguous 1..k, no gap)
        driver_a_sequences = sorted([o["sequence"] for o in driver_a_orders_after])
        expected_a = list(range(1, len(driver_a_sequences) + 1))
        if driver_a_sequences != expected_a:
            log_fail(f"Driver A sequences {driver_a_sequences} not contiguous from 1 (expected {expected_a})")
            return False
        
        log_pass(f"Driver A ({driver_a['name']}) remaining orders re-sequenced: {driver_a_sequences}")
        
        # Verify driver B's orders were re-sequenced including the new one
        driver_b_sequences = sorted([o["sequence"] for o in driver_b_orders_after])
        expected_b = list(range(1, len(driver_b_sequences) + 1))
        if driver_b_sequences != expected_b:
            log_fail(f"Driver B sequences {driver_b_sequences} not contiguous from 1 (expected {expected_b})")
            return False
        
        log_pass(f"Driver B ({driver_b['name']}) orders re-sequenced including new order: {driver_b_sequences}")
        
        # Verify all orders have eta
        errors = []
        for order in driver_a_orders_after + driver_b_orders_after:
            if not order.get("eta"):
                errors.append(f"Order {order['order_no']}: missing eta")
        
        if errors:
            for err in errors:
                log_fail(err)
            return False
        
        log_pass("Both source and target routes recomputed successfully with contiguous sequences and valid eta")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def test_4_unassign():
    """Test 4: UNASSIGN - POST /api/orders/assign {"order_id":"<id>","driver_id":null}"""
    log_test("4. UNASSIGN - Unassign a scheduled order")
    
    try:
        # Get a scheduled order
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get orders failed: {response.status_code}")
            return False
        
        orders = response.json()
        scheduled = [o for o in orders if o["status"] == "scheduled"]
        
        if not scheduled:
            log_fail("No scheduled orders found")
            return False
        
        order_to_unassign = scheduled[0]
        driver_id = order_to_unassign["assigned_driver_id"]
        log_info(f"Unassigning order: {order_to_unassign['order_no']} (id: {order_to_unassign['id'][:8]}...) from driver {driver_id[:8]}...")
        
        # Get driver's orders before unassign
        driver_orders_before = [o for o in orders if o.get("assigned_driver_id") == driver_id and o["status"] == "scheduled"]
        log_info(f"Driver has {len(driver_orders_before)} orders before unassign")
        
        # Unassign order
        payload = {"order_id": order_to_unassign["id"], "driver_id": None}
        response = requests.post(f"{BASE_URL}/orders/assign", json=payload, timeout=10)
        
        if response.status_code != 200:
            log_fail(f"Unassign failed: {response.status_code}")
            log_info(f"Response: {response.text}")
            return False
        
        unassigned_order = response.json()
        log_info(f"Unassign response: order_no={unassigned_order['order_no']}, status={unassigned_order['status']}, assigned_driver_id={unassigned_order.get('assigned_driver_id')}, sequence={unassigned_order.get('sequence')}, eta={unassigned_order.get('eta')}, late={unassigned_order.get('late')}")
        
        # Verify order is now unscheduled
        if unassigned_order["status"] != "unscheduled":
            log_fail(f"Order status={unassigned_order['status']}, expected 'unscheduled'")
            return False
        
        if unassigned_order.get("assigned_driver_id") is not None:
            log_fail(f"Order assigned_driver_id={unassigned_order.get('assigned_driver_id')}, expected None")
            return False
        
        if unassigned_order.get("sequence") is not None:
            log_fail(f"Order sequence={unassigned_order.get('sequence')}, expected None")
            return False
        
        if unassigned_order.get("eta") is not None:
            log_fail(f"Order eta={unassigned_order.get('eta')}, expected None")
            return False
        
        if unassigned_order.get("late") != False:
            log_fail(f"Order late={unassigned_order.get('late')}, expected False")
            return False
        
        log_pass(f"Order unassigned: status=unscheduled, assigned_driver_id=None, sequence=None, eta=None, late=False")
        
        # Verify former driver's remaining orders were re-sequenced
        response = requests.get(f"{BASE_URL}/orders", params={"date": test_data["today"]}, timeout=10)
        if response.status_code != 200:
            log_fail(f"Get orders failed: {response.status_code}")
            return False
        
        orders = response.json()
        driver_orders_after = [o for o in orders if o.get("assigned_driver_id") == driver_id and o["status"] == "scheduled"]
        
        log_info(f"Driver has {len(driver_orders_after)} orders after unassign")
        
        # Verify driver has one less order
        if len(driver_orders_after) != len(driver_orders_before) - 1:
            log_fail(f"Driver should have {len(driver_orders_before) - 1} orders, has {len(driver_orders_after)}")
            return False
        
        # Verify sequences are contiguous
        if driver_orders_after:
            sequences = sorted([o["sequence"] for o in driver_orders_after])
            expected = list(range(1, len(sequences) + 1))
            if sequences != expected:
                log_fail(f"Driver sequences {sequences} not contiguous from 1 (expected {expected})")
                return False
            
            log_pass(f"Former driver's remaining orders re-sequenced contiguously: {sequences}")
        else:
            log_pass("Former driver has no remaining orders")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {str(e)}")
        return False


def main():
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}Backend Reoptimization Features Test Suite{Colors.END}")
    print(f"{Colors.BLUE}Base URL: {BASE_URL}{Colors.END}")
    print(f"{Colors.BLUE}Test Date: {test_data['today']}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")
    
    # Setup
    if not setup_data():
        print(f"\n{Colors.RED}{'='*80}{Colors.END}")
        print(f"{Colors.RED}SETUP FAILED - Cannot proceed with tests{Colors.END}")
        print(f"{Colors.RED}{'='*80}{Colors.END}")
        return 1
    
    tests = [
        ("Reoptimize all drivers", test_1_reoptimize_all),
        ("Reoptimize one driver", test_2_reoptimize_one_driver),
        ("Assign recomputes both source and target", test_3_assign_recomputes_both_source_and_target),
        ("Unassign order", test_4_unassign),
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
