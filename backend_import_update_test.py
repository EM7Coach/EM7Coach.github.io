#!/usr/bin/env python3
"""
Focused test for /api/orders/import-update endpoint
Testing driver auto-assignment via "livreur" column and amount:null handling
"""
import requests
import json
from datetime import datetime

BASE_URL = "https://route-optimizer-464.preview.emergentagent.com/api"

def main():
    print("\n" + "="*80)
    print("IMPORT-UPDATE ENDPOINT TEST - Driver Auto-Assignment")
    print("="*80)
    
    # SETUP: POST /api/seed
    print("\n[SETUP] Step 1: POST /api/seed")
    seed_resp = requests.post(f"{BASE_URL}/seed")
    if seed_resp.status_code != 200:
        print(f"❌ SEED FAILED: {seed_resp.status_code} - {seed_resp.text}")
        return
    seed_data = seed_resp.json()
    print(f"✓ Seed successful: {json.dumps(seed_data, indent=2)}")
    
    # Get today's date
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"\n[SETUP] Using date: {today}")
    
    # SETUP: POST /api/optimize
    print(f"\n[SETUP] Step 2: POST /api/optimize with date={today}")
    opt_resp = requests.post(f"{BASE_URL}/optimize", json={"date": today})
    if opt_resp.status_code != 200:
        print(f"❌ OPTIMIZE FAILED: {opt_resp.status_code} - {opt_resp.text}")
        return
    opt_data = opt_resp.json()
    print(f"✓ Optimize successful: {json.dumps(opt_data, indent=2)}")
    
    # TEST 1: Import-update with 3 rows (2 existing + 1 new with new driver)
    print("\n" + "="*80)
    print("TEST 1: Import-update with driver assignments")
    print("="*80)
    
    import_payload = {
        "date": today,
        "rows": [
            {
                "order_no": "PL255425",
                "customer": "Pharmacie de l'Epte",
                "driver": "Hélène"
            },
            {
                "order_no": "PL255432",
                "customer": "Pharmacie Principale",
                "driver": "Isam"
            },
            {
                "customer": "Pharmacie Nouvelle Zone",
                "address": "Melun (77)",
                "amount": 80,
                "driver": "Patrick"
            }
        ]
    }
    
    print(f"\n[TEST 1] POST /api/orders/import-update")
    print(f"Payload: {json.dumps(import_payload, indent=2)}")
    
    import_resp = requests.post(f"{BASE_URL}/orders/import-update", json=import_payload)
    if import_resp.status_code != 200:
        print(f"❌ IMPORT-UPDATE FAILED: {import_resp.status_code} - {import_resp.text}")
        return
    
    import_data = import_resp.json()
    print(f"\n✓ Import-update response: {json.dumps(import_data, indent=2)}")
    
    # Verify response structure
    print("\n[VERIFY] Response structure:")
    assert "updated" in import_data, "Missing 'updated' field"
    assert "created" in import_data, "Missing 'created' field"
    assert "assigned" in import_data, "Missing 'assigned' field"
    assert "drivers_created" in import_data, "Missing 'drivers_created' field"
    print(f"  ✓ All required fields present")
    
    # Verify counts
    print("\n[VERIFY] Response counts:")
    print(f"  - updated: {import_data['updated']} (expected >= 2)")
    print(f"  - created: {import_data['created']} (expected >= 1)")
    print(f"  - assigned: {import_data['assigned']} (expected == 3)")
    print(f"  - drivers_created: {import_data['drivers_created']}")
    
    assert import_data["updated"] >= 2, f"Expected updated >= 2, got {import_data['updated']}"
    assert import_data["created"] >= 1, f"Expected created >= 1, got {import_data['created']}"
    assert import_data["assigned"] == 3, f"Expected assigned == 3, got {import_data['assigned']}"
    assert "Patrick" in import_data["drivers_created"], f"Expected 'Patrick' in drivers_created, got {import_data['drivers_created']}"
    print(f"  ✓ All counts correct, Patrick created")
    
    # GET /api/orders to verify assignments
    print("\n[VERIFY] GET /api/orders?date=" + today)
    orders_resp = requests.get(f"{BASE_URL}/orders", params={"date": today})
    if orders_resp.status_code != 200:
        print(f"❌ GET ORDERS FAILED: {orders_resp.status_code} - {orders_resp.text}")
        return
    
    orders = orders_resp.json()
    print(f"✓ Retrieved {len(orders)} orders")
    
    # GET /api/drivers to get driver IDs
    print("\n[VERIFY] GET /api/drivers")
    drivers_resp = requests.get(f"{BASE_URL}/drivers")
    if drivers_resp.status_code != 200:
        print(f"❌ GET DRIVERS FAILED: {drivers_resp.status_code} - {drivers_resp.text}")
        return
    
    drivers = drivers_resp.json()
    print(f"✓ Retrieved {len(drivers)} drivers")
    
    # Build driver name -> id map
    driver_map = {d["name"]: d for d in drivers}
    
    # Verify Hélène exists
    if "Hélène" not in driver_map:
        print(f"❌ Driver 'Hélène' not found in drivers list")
        return
    helene = driver_map["Hélène"]
    print(f"\n  Driver Hélène: id={helene['id']}, login_code={helene.get('login_code', 'N/A')}")
    
    # Verify Isam exists
    if "Isam" not in driver_map:
        print(f"❌ Driver 'Isam' not found in drivers list")
        return
    isam = driver_map["Isam"]
    print(f"  Driver Isam: id={isam['id']}, login_code={isam.get('login_code', 'N/A')}")
    
    # Verify Patrick was created
    if "Patrick" not in driver_map:
        print(f"❌ Driver 'Patrick' not found in drivers list (should have been auto-created)")
        return
    patrick = driver_map["Patrick"]
    print(f"  Driver Patrick: id={patrick['id']}, login_code={patrick.get('login_code', 'N/A')}")
    assert patrick.get("login_code"), "Patrick should have a login_code"
    print(f"  ✓ Patrick has login_code: {patrick['login_code']}")
    
    # Verify PL255425 assigned to Hélène
    print("\n[VERIFY] Order PL255425 (Pharmacie de l'Epte)")
    pl255425 = next((o for o in orders if o["order_no"] == "PL255425"), None)
    if not pl255425:
        print(f"❌ Order PL255425 not found")
        return
    
    print(f"  - customer: {pl255425['customer']}")
    print(f"  - assigned_driver_id: {pl255425['assigned_driver_id']}")
    print(f"  - expected driver_id: {helene['id']} (Hélène)")
    print(f"  - status: {pl255425['status']}")
    print(f"  - sequence: {pl255425['sequence']}")
    print(f"  - eta: {pl255425['eta']}")
    
    assert pl255425["assigned_driver_id"] == helene["id"], f"PL255425 should be assigned to Hélène, got {pl255425['assigned_driver_id']}"
    assert pl255425["status"] == "scheduled", f"PL255425 should be scheduled, got {pl255425['status']}"
    assert pl255425["sequence"] is not None, "PL255425 should have sequence"
    assert pl255425["eta"] is not None, "PL255425 should have eta"
    print(f"  ✓ PL255425 correctly assigned to Hélène with sequence and eta")
    
    # Verify PL255432 assigned to Isam
    print("\n[VERIFY] Order PL255432 (Pharmacie Principale)")
    pl255432 = next((o for o in orders if o["order_no"] == "PL255432"), None)
    if not pl255432:
        print(f"❌ Order PL255432 not found")
        return
    
    print(f"  - customer: {pl255432['customer']}")
    print(f"  - assigned_driver_id: {pl255432['assigned_driver_id']}")
    print(f"  - expected driver_id: {isam['id']} (Isam)")
    print(f"  - status: {pl255432['status']}")
    print(f"  - sequence: {pl255432['sequence']}")
    print(f"  - eta: {pl255432['eta']}")
    
    assert pl255432["assigned_driver_id"] == isam["id"], f"PL255432 should be assigned to Isam, got {pl255432['assigned_driver_id']}"
    assert pl255432["status"] == "scheduled", f"PL255432 should be scheduled, got {pl255432['status']}"
    assert pl255432["sequence"] is not None, "PL255432 should have sequence"
    assert pl255432["eta"] is not None, "PL255432 should have eta"
    print(f"  ✓ PL255432 correctly assigned to Isam with sequence and eta")
    
    # Verify Pharmacie Nouvelle Zone assigned to Patrick
    print("\n[VERIFY] Order 'Pharmacie Nouvelle Zone' (new order)")
    nouvelle = next((o for o in orders if o["customer"] == "Pharmacie Nouvelle Zone"), None)
    if not nouvelle:
        print(f"❌ Order 'Pharmacie Nouvelle Zone' not found")
        return
    
    print(f"  - order_no: {nouvelle['order_no']}")
    print(f"  - customer: {nouvelle['customer']}")
    print(f"  - address: {nouvelle['address']}")
    print(f"  - amount: {nouvelle['amount']}")
    print(f"  - lat: {nouvelle['lat']}, lng: {nouvelle['lng']}")
    print(f"  - assigned_driver_id: {nouvelle['assigned_driver_id']}")
    print(f"  - expected driver_id: {patrick['id']} (Patrick)")
    print(f"  - status: {nouvelle['status']}")
    print(f"  - sequence: {nouvelle['sequence']}")
    print(f"  - eta: {nouvelle['eta']}")
    
    assert nouvelle["assigned_driver_id"] == patrick["id"], f"Pharmacie Nouvelle Zone should be assigned to Patrick, got {nouvelle['assigned_driver_id']}"
    assert nouvelle["status"] == "scheduled", f"Pharmacie Nouvelle Zone should be scheduled, got {nouvelle['status']}"
    assert nouvelle["sequence"] is not None, "Pharmacie Nouvelle Zone should have sequence"
    assert nouvelle["eta"] is not None, "Pharmacie Nouvelle Zone should have eta"
    
    # Verify geocoding (Melun is in Île-de-France, lat 48-49.2, lng 1.4-3.2)
    assert 48.0 <= nouvelle["lat"] <= 49.2, f"Lat {nouvelle['lat']} out of IDF bounds (48-49.2)"
    assert 1.4 <= nouvelle["lng"] <= 3.2, f"Lng {nouvelle['lng']} out of IDF bounds (1.4-3.2)"
    print(f"  ✓ Pharmacie Nouvelle Zone correctly assigned to Patrick (new driver) with sequence, eta, and geocoded coordinates in IDF bounds")
    
    # TEST 2: amount: null case (row WITHOUT amount field)
    print("\n" + "="*80)
    print("TEST 2: Import-update with row WITHOUT amount field (should NOT cause 422)")
    print("="*80)
    
    import_payload_no_amount = {
        "date": today,
        "rows": [
            {
                "order_no": "PL255423",
                "customer": "Pharmacie de la Santé",
                "driver": "Aline"
            }
        ]
    }
    
    print(f"\n[TEST 2] POST /api/orders/import-update (no amount field)")
    print(f"Payload: {json.dumps(import_payload_no_amount, indent=2)}")
    
    import_resp2 = requests.post(f"{BASE_URL}/orders/import-update", json=import_payload_no_amount)
    print(f"\n  Response status: {import_resp2.status_code}")
    
    if import_resp2.status_code == 422:
        print(f"❌ FAILED: Got 422 (Unprocessable Entity) when amount field is missing")
        print(f"   Response: {import_resp2.text}")
        return
    
    if import_resp2.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {import_resp2.status_code}")
        print(f"   Response: {import_resp2.text}")
        return
    
    import_data2 = import_resp2.json()
    print(f"  ✓ Response 200 (not 422): {json.dumps(import_data2, indent=2)}")
    
    # Verify Aline assignment
    print("\n[VERIFY] Order PL255423 assigned to Aline")
    orders_resp2 = requests.get(f"{BASE_URL}/orders", params={"date": today})
    if orders_resp2.status_code != 200:
        print(f"❌ GET ORDERS FAILED: {orders_resp2.status_code}")
        return
    
    orders2 = orders_resp2.json()
    pl255423 = next((o for o in orders2 if o["order_no"] == "PL255423"), None)
    if not pl255423:
        print(f"❌ Order PL255423 not found")
        return
    
    aline = driver_map.get("Aline")
    if not aline:
        print(f"❌ Driver 'Aline' not found")
        return
    
    print(f"  - assigned_driver_id: {pl255423['assigned_driver_id']}")
    print(f"  - expected driver_id: {aline['id']} (Aline)")
    print(f"  - status: {pl255423['status']}")
    
    assert pl255423["assigned_driver_id"] == aline["id"], f"PL255423 should be assigned to Aline, got {pl255423['assigned_driver_id']}"
    assert pl255423["status"] == "scheduled", f"PL255423 should be scheduled, got {pl255423['status']}"
    print(f"  ✓ PL255423 correctly assigned to Aline (no 422 error for missing amount)")
    
    # FINAL SUMMARY
    print("\n" + "="*80)
    print("🎉 ALL TESTS PASSED!")
    print("="*80)
    print("\nSUMMARY:")
    print("✅ TEST 1: Import-update with driver assignments")
    print("   - updated >= 2 orders (PL255425, PL255432)")
    print("   - created >= 1 order (Pharmacie Nouvelle Zone)")
    print("   - assigned == 3 orders")
    print("   - drivers_created contains 'Patrick'")
    print("   - PL255425 assigned to Hélène with sequence/eta")
    print("   - PL255432 assigned to Isam with sequence/eta")
    print("   - Pharmacie Nouvelle Zone assigned to Patrick (new driver) with sequence/eta")
    print("   - Patrick has login_code in /api/drivers")
    print("   - Pharmacie Nouvelle Zone geocoded to IDF bounds")
    print("")
    print("✅ TEST 2: amount: null case")
    print("   - POST /api/orders/import-update with row WITHOUT amount field returns 200 (not 422)")
    print("   - Order PL255423 assigned to Aline successfully")
    print("")
    print("✅ No 422/500 errors detected")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\n❌ ASSERTION FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
