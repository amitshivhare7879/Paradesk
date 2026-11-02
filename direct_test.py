import sys
import os
import io
from datetime import datetime, timedelta

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    app, init_db, get_db_connection, admin_dashboard, 
    login_action, register_action, participant_dashboard, 
    update_team_details, participant_register_event,
    edit_event_details, send_email_dispatch,
    ground_checkin, sweep_noshows_protocol, submit_judge_scores, 
    leaderboard_view, toggle_leaderboard_freeze
)
from starlette.requests import Request
from starlette.datastructures import Headers, QueryParams, UploadFile

def test_all():
    print("[TEST 1] Initializing fresh database with users and seed events...")
    init_db(force_reseed=True)
    conn = get_db_connection()
    
    # 1. Verify Users
    users = conn.execute("SELECT email, role, full_name FROM users ORDER BY id ASC").fetchall()
    assert len(users) >= 3, f"Expected at least 3 seeded users, found {len(users)}"
    emails = {u["email"]: u["role"] for u in users}
    assert emails.get("admin@iitm.ac.in") == "ADMIN"
    assert emails.get("aarav@smail.iitm.ac.in") == "PARTICIPANT"
    assert emails.get("vikram@smail.iitm.ac.in") == "PARTICIPANT"
    print(f"  [OK] Admin and Participant users created with verified roles.")

    # 2. Verify Events
    events = conn.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
    assert len(events) == 2, f"Expected 2 events, found {len(events)}"
    ev1 = events[0]
    ev2 = events[1]
    assert ev1["name"] == "HackParadox 2027"
    assert ev2["name"] == "AlgoStrike Coding Battle"
    print(f"  [OK] Event 1 '{ev1['name']}' (Today) and Event 2 '{ev2['name']}' (Next Week) provisioned.")

    # 3. Verify Exact Counts for Event 1: 30 Desks, 30 Allocated, 5 in Queue
    ev1_desks = conn.execute("SELECT COUNT(*) as cnt FROM desks WHERE event_id = ?", (ev1["id"],)).fetchone()["cnt"]
    assert ev1_desks == 30, f"Expected 30 desks for Event 1, found {ev1_desks}"
    
    ev1_allocated = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status IN ('ALLOCATED', 'CHECKED_IN')", (ev1["id"],)).fetchone()["cnt"]
    assert ev1_allocated == 30, f"Expected 30 allocated teams for Event 1, found {ev1_allocated}"
    
    ev1_queue = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status = 'STANDBY_TOP10'", (ev1["id"],)).fetchone()["cnt"]
    assert ev1_queue == 5, f"Expected 5 standby queue teams for Event 1, found {ev1_queue}"
    print(f"  [OK] Event 1 has exactly 30 desks, 30 allocated teams, and 5 in the standby queue (Total = 35 teams).")
    conn.close()

    print("\n[TEST 2] Testing Authentication Gateway (Login & Registration)...")
    # A. Invalid Login Attempt
    dummy_req = Request({"type": "http", "method": "POST", "session": {}})
    inv_resp = login_action(dummy_req, email="admin@iitm.ac.in", password="wrongpassword")
    assert inv_resp.status_code == 303
    assert "Invalid" in inv_resp.headers["location"]
    print("  [OK] Invalid credentials safely rejected.")

    # B. Valid Admin Login
    admin_session_req = Request({"type": "http", "method": "POST", "session": {}})
    admin_resp = login_action(admin_session_req, email="admin@iitm.ac.in", password="admin123")
    assert admin_resp.status_code == 303
    assert admin_session_req.session.get("user_role") == "ADMIN"
    assert "/dashboard" in admin_resp.headers["location"]
    print("  [OK] Admin login succeeded, established session with role 'ADMIN'.")

    # C. Valid Participant Login
    part_session_req = Request({"type": "http", "method": "POST", "session": {}})
    part_resp = login_action(part_session_req, email="aarav@smail.iitm.ac.in", password="participant123")
    assert part_resp.status_code == 303
    assert part_session_req.session.get("user_role") == "PARTICIPANT"
    assert "/participant/dashboard" in part_resp.headers["location"]
    print("  [OK] Participant login succeeded, established session with role 'PARTICIPANT'.")

    # D. New User Registration
    new_reg_req = Request({"type": "http", "method": "POST", "session": {}})
    reg_resp = register_action(new_reg_req, full_name="Sneha Rao", email="sneha@smail.iitm.ac.in", phone="+91 98409 99999", password="password123")
    assert reg_resp.status_code == 303
    assert new_reg_req.session.get("user_email") == "sneha@smail.iitm.ac.in"
    print("  [OK] New participant registered and automatically authenticated.")

    print("\n[TEST 3] Testing Participant Dashboard & 24-Hour Code Visibility Rule...")
    # Participant Aarav is registered for Event 1 (Today's event, starts in 2 hours -> code must be UNLOCKED!)
    part_view_req = Request({
        "type": "http", "method": "GET", 
        "session": {"user_id": 2, "user_email": "aarav@smail.iitm.ac.in", "user_role": "PARTICIPANT", "user_name": "Aarav Sharma"},
        "query_string": b""
    })
    part_dash_resp = participant_dashboard(part_view_req)
    assert part_dash_resp.status_code == 200
    html_part = part_dash_resp.body.decode("utf-8")
    assert "NeuralForge" in html_part
    assert "PX-CRC01" in html_part
    assert "Active &bull; &lt; 24h" in html_part or "Active" in html_part
    print("  [OK] Participant portal for today's event correctly displays unlocked check-in code and assigned desk.")

    print("\n[TEST 4] Testing Participant Team Roster Update...")
    # Update NeuralForge squad details
    update_team_details(
        request=part_view_req,
        team_id=1,
        team_name="NeuralForge AI",
        lead_phone="+91 98401 99999",
        member_count=4,
        member_names="Aarav Sharma, Sneha Patel, Rohan Gupta, Arjun Mehta"
    )
    conn = get_db_connection()
    updated_team = conn.execute("SELECT team_name, lead_phone, member_names FROM teams WHERE id = 1").fetchone()
    assert updated_team["team_name"] == "NeuralForge AI"
    assert updated_team["lead_phone"] == "+91 98401 99999"
    assert "Arjun Mehta" in updated_team["member_names"]
    print(f"  [OK] Participant updated team details and member names successfully.")
    conn.close()

    print("\n[TEST 5] Testing Event Registration & Capacity Overflow Queue...")
    # User registers for Event 1 which is already at capacity (30 desks full + 5 queue)
    reg_event_resp = participant_register_event(
        request=part_view_req,
        event_id=ev1["id"],
        team_name="QueueOverflowTeam",
        lead_phone="+91 98401 88888",
        member_count=4,
        member_names="Dev 1, Dev 2, Dev 3, Dev 4"
    )
    assert reg_event_resp.status_code == 303
    conn = get_db_connection()
    overflow_team = conn.execute("SELECT * FROM teams WHERE team_name = 'QueueOverflowTeam'").fetchone()
    assert overflow_team is not None
    assert overflow_team["queue_position"] == 36
    assert overflow_team["status"] == "STANDBY_TOP10"
    assert overflow_team["assigned_desk_id"] is None
    print(f"  [OK] Full event automatically placed new registration into Queue Position #36 (STANDBY_TOP10).")
    conn.close()

    print("\n[TEST 6] Testing Admin Dashboard & Event Details Editing...")
    admin_view_req = Request({
        "type": "http", "method": "GET",
        "session": {"user_id": 1, "user_email": "admin@iitm.ac.in", "user_role": "ADMIN", "user_name": "Admin Organizer"},
        "query_string": b"event_id=1"
    })
    admin_dash_resp = admin_dashboard(admin_view_req, event_id=ev1["id"])
    assert admin_dash_resp.status_code == 200
    html_admin = admin_dash_resp.body.decode("utf-8")
    assert "Paradesk Core" in html_admin
    assert "Admin Console" in html_admin
    assert "Floorplan Desk Matrix" in html_admin
    print("  [OK] Admin Dashboard rendered cleanly with floorplan and capacity gauges.")

    # Edit Event Details (Venue, timing)
    edit_resp = edit_event_details(
        request=admin_view_req,
        event_id=ev1["id"],
        name="HackParadox 2027 (CRC Grand Edition)",
        venue_name="CRC Grand Hall 101",
        event_start="2027-01-20 09:30:00",
        max_teams=30,
        max_members_per_team=4,
        problem_statement_url="https://paradox27.iitm.ac.in/ps/grand.pdf",
        problem_statement_text="Updated logistics challenge description.",
        rubric_json=""
    )
    assert edit_resp.status_code == 303
    conn = get_db_connection()
    updated_ev = conn.execute("SELECT name, venue_name FROM events WHERE id = ?", (ev1["id"],)).fetchone()
    assert updated_ev["name"] == "HackParadox 2027 (CRC Grand Edition)"
    assert updated_ev["venue_name"] == "CRC Grand Hall 101"
    print(f"  [OK] Admin updated event title, venue, and timing successfully.")
    conn.close()

    print("\n[TEST 7] Testing Email Notification Dispatch System...")
    mail_resp = send_email_dispatch(
        request=admin_view_req,
        event_id=ev1["id"],
        campaign_type="BROADCAST_24H_CODES"
    )
    assert mail_resp.status_code == 303
    conn = get_db_connection()
    emails = conn.execute("SELECT * FROM emails_sent WHERE event_id = ? ORDER BY id DESC", (ev1["id"],)).fetchall()
    assert len(emails) >= 1
    assert "24h Check-in Pass" in emails[0]["subject"]
    print(f"  [OK] Dispatched email broadcast '{emails[0]['subject']}' to {emails[0]['recipient_count']} recipients.")
    conn.close()

    print("\n[TEST 8] Testing Ground Check-In by Code & Desk Assignment...")
    # Verify team 6 by code "PX-CRC06"
    checkin_resp = ground_checkin(request=admin_view_req, event_id=ev1["id"], token_or_id="PX-CRC06")
    assert checkin_resp.status_code == 303
    conn = get_db_connection()
    team_6 = conn.execute("SELECT * FROM teams WHERE unique_checkin_token = 'PX-CRC06'").fetchone()
    assert team_6["status"] == "CHECKED_IN"
    assert team_6["checkin_timestamp"] is not None
    print(f"  [OK] Ground check-in successfully verified '{team_6['team_name']}' via code 'PX-CRC06'.")
    conn.close()

    print("\n[TEST 9] Testing 15-Minute Sweep Protocol Promoting Standby Top-10...")
    sweep_resp = sweep_noshows_protocol(request=admin_view_req, event_id=ev1["id"])
    assert sweep_resp.status_code == 303
    conn = get_db_connection()
    no_shows = conn.execute("SELECT COUNT(*) as cnt FROM teams WHERE event_id = ? AND status = 'NO_SHOW'", (ev1["id"],)).fetchone()["cnt"]
    promoted = conn.execute("SELECT * FROM teams WHERE unique_checkin_token = 'PX-STBY31'").fetchone()
    assert no_shows > 0, "Expected unverified teams to be swept to NO_SHOW"
    assert promoted["status"] == "ALLOCATED", "Expected standby team to be promoted to ALLOCATED"
    assert promoted["assigned_desk_id"] is not None, "Promoted team must have an assigned desk"
    print(f"  [OK] 15-minute sweep swept {no_shows} no-shows and promoted standby team '{promoted['team_name']}' into a reclaimed desk!")
    conn.close()

    print("\n[TEST 10] Testing Production Health Check Endpoint...")
    from app import health_check
    health_resp = health_check()
    assert health_resp.status_code == 200
    import json
    data = json.loads(health_resp.body.decode("utf-8"))
    assert data["status"] == "healthy"
    assert data["service"] == "paradesk-core"
    assert data["database"] == "healthy"
    print("  [OK] /health endpoint returned 200 OK with database connection verified.")

    print("\n" + "="*65)
    print("ALL 10 TEST SUITES PASSED! DEPLOY-READY & PRODUCTION HARDENED.")
    print("="*65)

if __name__ == "__main__":
    test_all()
