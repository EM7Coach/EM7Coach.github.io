#!/usr/bin/env python3
"""
Backend API Test Suite for OptimoRoute Pharmacy App
Tests two NEW endpoints: Driver Login and Import-Update with Driver Auto-Detect
"""
import requests
import json
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://route-optimizer-464.preview.emergentagent.com/api"

def test_driver_login():
    """Test 1: DRIVER LOGIN endpoint"""
    print("\n" + "="*80)
    print("TEST 1: DRIVER LOGIN")
    print("="*80)
    
    # Setup: Seed data first
    print("\n[SETUP] Seeding data...")
    seed_resp = requests.post(f"{BASE_URL}/seed")
    assert seed_resp.status_code == 200, f"Seed failed: {seed_resp.status_code}"
    seed_data = seed_resp.json()
    print(f"✓ Seed successful: {seed_data}")
    assert seed_data["drivers"] == 6, f"Expected 6 drivers, got {seed_data['drivers']}"
    
    # Get today's date for optimize
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"\n[SETUP] Optimizing routes for {today}...")
    opt_resp = requests.post(f"{BASE_URL}/optimize", json={"date": today})
    assert opt_resp.status_code == 200, f"Optimize failed: {opt_resp.status_code}"
    opt_data = opt_resp.json()
    print(f"✓ Optimize successful: assigned={opt_data['assigned']}, unassigned={opt_data['unassigned']}")
    
    # Test 1a: Verify all drivers have login_code
    print("\n[TEST 1a] GET /api/drivers - verify login_code field")
    drivers_resp = requests.get(f"{BASE_URL}/drivers")
    assert drivers_resp.status_code == 200, f"GET /drivers failed: {drivers_resp.status_code}"
    drivers = drivers_resp.json()
    print(f"✓ Retrieved {len(drivers)} drivers")
    
    expected_codes = {"1111": "Deon", "2222": "Hélène", "3333": "Aline", "4444": "Kenan", "5555": "Isam", "6666": "Gédéon"}
    found_codes = {}
    
    for driver in drivers:
        assert "login_code" in driver, f"Driver {driver['name']} missing login_code field"
        assert driver["login_code"], f"Driver {driver['name']} has empty login_code"
        print(f"  - {driver['name']}: login_code={driver['login_code']}")
        found_codes[driver["login_code"]] = driver["name"]
    
    # Verify seed drivers have codes 1111-6666
    for code, expected_name in expected_codes.items():
        assert code in found_codes, f"Expected login_code {code} for {expected_name} not found"
        assert found_codes[code] == expected_name, f"Code {code} assigned to {found_codes[code]}, expected {expected_name}"
    
    print(f"✓ All 6 drivers have correct login_codes (1111-6666)")
    
    # Test 1b: Valid login with code "1111" (Deon)
    print("\n[TEST 1b] POST /api/driver/login with valid code '1111'")
    login_resp = requests.post(f"{BASE_URL}/driver/login", json={"code": "1111"})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code} - {login_resp.text}"
    driver = login_resp.json()
    print(f"✓ Login successful: {json.dumps(driver, indent=2)}")
    assert driver["name"] == "Deon", f"Expected driver name 'Deon', got '{driver['name']}'"
    assert driver["login_code"] == "1111", f"Expected login_code '1111', got '{driver['login_code']}'"
    print(f"✓ Returned driver object for Deon with login_code 1111")
    
    # Test 1c: Invalid login with code "0000"
    print("\n[TEST 1c] POST /api/driver/login with invalid code '0000'")
    invalid_resp = requests.post(f"{BASE_URL}/driver/login", json={"code": "0000"})
    assert invalid_resp.status_code == 401, f"Expected 401, got {invalid_resp.status_code}"
    print(f"✓ Invalid code correctly returns 401: {invalid_resp.json()}")
    
    print("\n" + "="*80)
    print("✅ TEST 1 PASSED: DRIVER LOGIN working correctly")
    print("="*80)
    return drivers


def test_import_update_with_driver_auto_detect(drivers):
    """Test 2: IMPORT-UPDATE WITH DRIVER AUTO-DETECT endpoint"""
    print("\n" + "="*80)
    print("TEST 2: IMPORT-UPDATE WITH DRIVER AUTO-DETECT")
    print("="*80)
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Find Aline and Kenan driver IDs
    aline = next((d for d in drivers if d["name"] == "Aline"), None)
    kenan = next((d for d in drivers if d["name"] == "Kenan"), None)
    assert aline, "Aline driver not found"
    assert kenan, "Kenan driver not found"
    print(f"\n[SETUP] Found drivers: Aline (id={aline['id']}), Kenan (id={kenan['id']})")
    
    # Test 2a: Import-update with existing orders and new driver
    print("\n[TEST 2a] POST /api/orders/import-update with 3 rows")
    import_payload = {
        "date": today,
        "rows": [
            {
                "order_no": "PL255423",
                "customer": "Pharmacie de la Santé",
                "amount": 450,
                "colis_cold": 2,
                "driver": "Aline"
            },
            {
                "order_no": "PL255424",
                "customer": "Pharmacie Hammou",
                "driver": "Kenan"
            },
            {
                "customer": "Pharmacie Toute Nouvelle",
                "address": "Meaux (77)",
                "amount": 120,
                "driver": "Livreur Inconnu"
            }
        ]
    }
    
    print(f"Payload: {json.dumps(import_payload, indent=2)}")
    import_resp = requests.post(f"{BASE_URL}/orders/import-update", json=import_payload)
    assert import_resp.status_code == 200, f"Import-update failed: {import_resp.status_code} - {import_resp.text}"
    import_data = import_resp.json()
    print(f"✓ Import-update response: {json.dumps(import_data, indent=2)}")
    
    # Verify response structure
    assert "updated" in import_data, "Missing 'updated' in response"
    assert "created" in import_data, "Missing 'created' in response"
    assert "assigned" in import_data, "Missing 'assigned' in response"
    assert "geocoded" in import_data, "Missing 'geocoded' in response"
    assert "drivers_created" in import_data, "Missing 'drivers_created' in response"
    
    # Verify counts
    assert import_data["updated"] == 2, f"Expected updated=2, got {import_data['updated']}"
    assert import_data["created"] == 1, f"Expected created=1, got {import_data['created']}"
    assert "Livreur Inconnu" in import_data["drivers_created"], f"Expected 'Livreur Inconnu' in drivers_created, got {import_data['drivers_created']}"
    print(f"✓ Correct counts: updated=2, created=1, drivers_created contains 'Livreur Inconnu'")
    
    # Test 2b: Verify updated orders
    print("\n[TEST 2b] GET /api/orders - verify updated orders")
    orders_resp = requests.get(f"{BASE_URL}/orders", params={"date": today})
    assert orders_resp.status_code == 200, f"GET /orders failed: {orders_resp.status_code}"
    orders = orders_resp.json()
    print(f"✓ Retrieved {len(orders)} orders for {today}")
    
    # Find PL255423 (updated with amount=450, colis_cold=2, assigned to Aline)
    pl255423 = next((o for o in orders if o["order_no"] == "PL255423"), None)
    assert pl255423, "Order PL255423 not found"
    print(f"\n  Order PL255423:")
    print(f"    - amount: {pl255423['amount']} (expected 450)")
    print(f"    - colis_cold: {pl255423['colis_cold']} (expected 2)")
    print(f"    - assigned_driver_id: {pl255423['assigned_driver_id']} (expected {aline['id']})")
    print(f"    - status: {pl255423['status']} (expected 'scheduled')")
    print(f"    - sequence: {pl255423['sequence']}")
    print(f"    - eta: {pl255423['eta']}")
    
    assert pl255423["amount"] == 450, f"Expected amount=450, got {pl255423['amount']}"
    assert pl255423["colis_cold"] == 2, f"Expected colis_cold=2, got {pl255423['colis_cold']}"
    assert pl255423["assigned_driver_id"] == aline["id"], f"Expected assigned to Aline, got {pl255423['assigned_driver_id']}"
    assert pl255423["status"] == "scheduled", f"Expected status='scheduled', got {pl255423['status']}"
    assert pl255423["sequence"] is not None, f"Expected sequence to be set, got None"
    assert pl255423["eta"] is not None, f"Expected eta to be set, got None"
    print(f"✓ PL255423 correctly updated and assigned to Aline with sequence/eta")
    
    # Find PL255424 (assigned to Kenan)
    pl255424 = next((o for o in orders if o["order_no"] == "PL255424"), None)
    assert pl255424, "Order PL255424 not found"
    print(f"\n  Order PL255424:")
    print(f"    - assigned_driver_id: {pl255424['assigned_driver_id']} (expected {kenan['id']})")
    print(f"    - status: {pl255424['status']} (expected 'scheduled')")
    print(f"    - sequence: {pl255424['sequence']}")
    print(f"    - eta: {pl255424['eta']}")
    
    assert pl255424["assigned_driver_id"] == kenan["id"], f"Expected assigned to Kenan, got {pl255424['assigned_driver_id']}"
    assert pl255424["status"] == "scheduled", f"Expected status='scheduled', got {pl255424['status']}"
    assert pl255424["sequence"] is not None, f"Expected sequence to be set, got None"
    assert pl255424["eta"] is not None, f"Expected eta to be set, got None"
    print(f"✓ PL255424 correctly assigned to Kenan with sequence/eta")
    
    # Find "Pharmacie Toute Nouvelle" (new order, assigned to new driver "Livreur Inconnu")
    nouvelle = next((o for o in orders if o["customer"] == "Pharmacie Toute Nouvelle"), None)
    assert nouvelle, "Order 'Pharmacie Toute Nouvelle' not found"
    print(f"\n  Order 'Pharmacie Toute Nouvelle':")
    print(f"    - order_no: {nouvelle['order_no']}")
    print(f"    - address: {nouvelle['address']}")
    print(f"    - amount: {nouvelle['amount']} (expected 120)")
    print(f"    - lat: {nouvelle['lat']}, lng: {nouvelle['lng']}")
    print(f"    - assigned_driver_id: {nouvelle['assigned_driver_id']}")
    print(f"    - status: {nouvelle['status']} (expected 'scheduled')")
    print(f"    - sequence: {nouvelle['sequence']}")
    print(f"    - eta: {nouvelle['eta']}")
    
    assert nouvelle["amount"] == 120, f"Expected amount=120, got {nouvelle['amount']}"
    assert nouvelle["status"] == "scheduled", f"Expected status='scheduled', got {nouvelle['status']}"
    assert nouvelle["sequence"] is not None, f"Expected sequence to be set, got None"
    assert nouvelle["eta"] is not None, f"Expected eta to be set, got None"
    
    # Verify geocoding (Meaux is in Île-de-France, lat 48-49.2, lng 1.4-3.2)
    assert 48.0 <= nouvelle["lat"] <= 49.2, f"Lat {nouvelle['lat']} out of Île-de-France bounds (48-49.2)"
    assert 1.4 <= nouvelle["lng"] <= 3.2, f"Lng {nouvelle['lng']} out of Île-de-France bounds (1.4-3.2)"
    print(f"✓ 'Pharmacie Toute Nouvelle' correctly created, geocoded within Île-de-France bounds, and assigned with sequence/eta")
    
    # Test 2c: Verify new driver "Livreur Inconnu" was created
    print("\n[TEST 2c] GET /api/drivers - verify new driver created")
    drivers_resp = requests.get(f"{BASE_URL}/drivers")
    assert drivers_resp.status_code == 200, f"GET /drivers failed: {drivers_resp.status_code}"
    all_drivers = drivers_resp.json()
    print(f"✓ Retrieved {len(all_drivers)} drivers (expected 7)")
    
    livreur = next((d for d in all_drivers if d["name"] == "Livreur Inconnu"), None)
    assert livreur, "Driver 'Livreur Inconnu' not found"
    print(f"\n  Driver 'Livreur Inconnu':")
    print(f"    - id: {livreur['id']}")
    print(f"    - login_code: {livreur['login_code']}")
    print(f"    - color: {livreur['color']}")
    print(f"    - status: {livreur['status']}")
    
    assert livreur["login_code"], f"Expected login_code to be set, got empty"
    assert len(livreur["login_code"]) >= 4, f"Expected login_code length >= 4, got {len(livreur['login_code'])}"
    print(f"✓ 'Livreur Inconnu' driver created with login_code: {livreur['login_code']}")
    
    # Verify nouvelle order is assigned to this new driver
    assert nouvelle["assigned_driver_id"] == livreur["id"], f"Expected 'Pharmacie Toute Nouvelle' assigned to 'Livreur Inconnu', got {nouvelle['assigned_driver_id']}"
    print(f"✓ 'Pharmacie Toute Nouvelle' correctly assigned to new driver 'Livreur Inconnu'")
    
    # Test 2d: Verify routes were recomputed (contiguous sequences)
    print("\n[TEST 2d] Verify affected drivers' routes have contiguous sequences")
    
    # Get all orders for Aline
    aline_orders = [o for o in orders if o["assigned_driver_id"] == aline["id"] and o["status"] == "scheduled"]
    aline_sequences = sorted([o["sequence"] for o in aline_orders if o["sequence"] is not None])
    print(f"\n  Aline's route: {len(aline_orders)} orders, sequences: {aline_sequences}")
    assert aline_sequences == list(range(1, len(aline_sequences) + 1)), f"Aline's sequences not contiguous: {aline_sequences}"
    print(f"✓ Aline's route has contiguous sequences starting at 1")
    
    # Get all orders for Kenan
    kenan_orders = [o for o in orders if o["assigned_driver_id"] == kenan["id"] and o["status"] == "scheduled"]
    kenan_sequences = sorted([o["sequence"] for o in kenan_orders if o["sequence"] is not None])
    print(f"\n  Kenan's route: {len(kenan_orders)} orders, sequences: {kenan_sequences}")
    assert kenan_sequences == list(range(1, len(kenan_sequences) + 1)), f"Kenan's sequences not contiguous: {kenan_sequences}"
    print(f"✓ Kenan's route has contiguous sequences starting at 1")
    
    # Get all orders for Livreur Inconnu
    livreur_orders = [o for o in orders if o["assigned_driver_id"] == livreur["id"] and o["status"] == "scheduled"]
    livreur_sequences = sorted([o["sequence"] for o in livreur_orders if o["sequence"] is not None])
    print(f"\n  Livreur Inconnu's route: {len(livreur_orders)} orders, sequences: {livreur_sequences}")
    assert livreur_sequences == list(range(1, len(livreur_sequences) + 1)), f"Livreur Inconnu's sequences not contiguous: {livreur_sequences}"
    print(f"✓ Livreur Inconnu's route has contiguous sequences starting at 1")
    
    # Test 2e: Login with new driver's code
    print("\n[TEST 2e] POST /api/driver/login with new driver's code")
    login_resp = requests.post(f"{BASE_URL}/driver/login", json={"code": livreur["login_code"]})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code} - {login_resp.text}"
    logged_driver = login_resp.json()
    print(f"✓ Login successful with code '{livreur['login_code']}'")
    assert logged_driver["name"] == "Livreur Inconnu", f"Expected driver name 'Livreur Inconnu', got '{logged_driver['name']}'"
    assert logged_driver["id"] == livreur["id"], f"Expected driver id {livreur['id']}, got {logged_driver['id']}"
    print(f"✓ Returned correct driver object for 'Livreur Inconnu'")
    
    print("\n" + "="*80)
    print("✅ TEST 2 PASSED: IMPORT-UPDATE WITH DRIVER AUTO-DETECT working correctly")
    print("="*80)


def main():
    """Run all backend tests"""
    print("\n" + "="*80)
    print("BACKEND API TEST SUITE - OptimoRoute Pharmacy App")
    print("Testing TWO NEW endpoints:")
    print("  1. Driver Login (GET /api/drivers, POST /api/driver/login)")
    print("  2. Import-Update with Driver Auto-Detect (POST /api/orders/import-update)")
    print("="*80)
    
    try:
        # Test 1: Driver Login
        drivers = test_driver_login()
        
        # Test 2: Import-Update with Driver Auto-Detect
        test_import_update_with_driver_auto_detect(drivers)
        
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED!")
        print("="*80)
        print("\nSUMMARY:")
        print("✅ Driver Login: All drivers have login_codes (1111-6666), valid login returns driver, invalid returns 401")
        print("✅ Import-Update: Updates existing orders, creates new orders, auto-creates drivers, assigns orders, geocodes addresses, recomputes routes")
        print("="*80 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
