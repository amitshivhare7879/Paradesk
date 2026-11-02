/**
 * PARADESK LITE — Google Sheets & Apps Script Companion
 * Engineered for IIT Madras Paradox'27 Technical Events
 * 
 * Instructions to Deploy:
 * 1. Create a Google Sheet with columns:
 *    A: TeamID | B: TeamName | C: LeadName | D: LeadEmail | E: LeadPhone | F: Status | G: DeskID | H: RSVPToken | I: CheckinTimestamp
 * 2. Click Extensions > Apps Script.
 * 3. Replace all code with this script and save.
 * 4. Refresh your Google Sheet to see the custom "⚡ Paradox'27 Ops" menu!
 */

// Configuration
const SHEET_NAME = "Registrations";
const VENUE_NAME = "Central Research Complex (CRC), IIT Madras";
const TOTAL_STANDARD_DESKS = 35;

/**
 * Creates custom menu in Google Sheets on open
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu("⚡ Paradox'27 Ops")
    .addItem("1. Initialize Sheet Headers & Sample Data", "initSheet")
    .addSeparator()
    .addItem("2. Send 48h Hard RSVP Reminders (MailApp)", "send48hRSVPEmails")
    .addItem("3. Send Squad-Rescue Health Check", "sendSquadRescueEmails")
    .addItem("4. Send Hostel Flash Broadcast", "sendHostelBroadcastEmails")
    .addSeparator()
    .addItem("5. 15-Minute No-Show Sweeper", "sweepNoShows")
    .addItem("6. Open Ground Check-in Scanner (Sidebar)", "showCheckinSidebar")
    .addToUi();
}

/**
 * Sets up clean headers and test teams
 */
function initSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  sheet.clear();

  const headers = [
    ["Team ID", "Team Name", "Lead Name", "Lead Email", "Lead Phone", "Status", "Desk ID", "RSVP Token", "Check-in Timestamp"]
  ];
  sheet.getRange(1, 1, 1, 9).setValues(headers).setFontWeight("bold").setBackground("#1e293b").setFontColor("#ffffff");

  const sampleTeams = [
    [1, "NeuralForge", "Aarav Sharma", Session.getActiveUser().getEmail(), "+91 98401 12345", "REGISTERED", "", "RSVP-NF01", ""],
    [2, "ByteCrafters", "Priya Raman", Session.getActiveUser().getEmail(), "+91 98402 23456", "REGISTERED", "", "RSVP-BC02", ""],
    [3, "AlgoRhythm", "Rohan Iyer", Session.getActiveUser().getEmail(), "+91 98403 34567", "CONFIRMED_RSVP", "", "RSVP-AR03", ""],
    [4, "QuantumCoders", "Sneha Patel", Session.getActiveUser().getEmail(), "+91 98404 45678", "REGISTERED", "", "RSVP-QC04", ""],
    [5, "LobbyStandby Squad", "Vikram Nair", Session.getActiveUser().getEmail(), "+91 98405 56789", "WAITLISTED", "", "RSVP-LS05", ""]
  ];
  sheet.getRange(2, 1, sampleTeams.length, 9).setValues(sampleTeams);
  sheet.autoResizeColumns(1, 9);
  SpreadsheetApp.getUi().alert("Sheet initialized with headers and 5 sample teams!");
}

/**
 * Dispatches automated 48h RSVP confirmation emails with personalized tokens
 */
function send48hRSVPEmails() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const data = sheet.getDataRange().getValues();
  let count = 0;

  for (let i = 1; i < data.length; i++) {
    const status = data[i][5];
    const email = data[i][3];
    const teamName = data[i][1];
    const leadName = data[i][2];
    const token = data[i][7];

    if (status === "REGISTERED" && email) {
      const subject = `[Action Required] 48-Hour Hard RSVP: Confirm Desk Slot for ${teamName}`;
      const body = `Hi ${leadName},\n\nYour team "${teamName}" is registered for the Paradox'27 Hackathon at ${VENUE_NAME}.\n\nBecause hall capacity is strictly capped at 35 tables with 1Gbps LAN drops, please reply with "CONFIRM" or click your verification token (${token}) to secure your desk.\n\nUnconfirmed tables will be dynamically released to our waitlisted students at T-18 hours.\n\nWarm-up Docker starter kit: https://github.com/paradox27/warmup-kit\n\nBest,\nTechnicals Department, Paradox'27`;

      MailApp.sendEmail(email, subject, body);
      count++;
    }
  }

  SpreadsheetApp.getUi().alert(`Sent 48h RSVP reminder emails to ${count} unconfirmed teams!`);
}

/**
 * Dispatches Squad-Rescue health check emails to catch dropouts before event day
 */
function sendSquadRescueEmails() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const data = sheet.getDataRange().getValues();
  let count = 0;

  for (let i = 1; i < data.length; i++) {
    const email = data[i][3];
    const teamName = data[i][1];
    const leadName = data[i][2];

    if (email) {
      const subject = `Team Health Check: Missing Members? Paradox'27 Squad-Rescue is Live`;
      const body = `Hi ${leadName},\n\nIs your squad "${teamName}" missing a member due to conflicting academic schedules? Don't back out!\n\nOur Squad-Rescue engine pairs solo coders and partial squads into complete 4-person teams. Reply to this email if you need reinforcements or want to merge.\n\nBest,\nTechnicals Department`;

      MailApp.sendEmail(email, subject, body);
      count++;
    }
  }

  SpreadsheetApp.getUi().alert(`Sent Squad-Rescue health check emails to ${count} teams!`);
}

/**
 * Sweeps inactive Registered/RSVP teams 15 minutes post-kickoff
 */
function sweepNoShows() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const data = sheet.getDataRange().getValues();
  let sweptCount = 0;

  for (let i = 1; i < data.length; i++) {
    const status = data[i][5];
    if (status === "REGISTERED" || status === "CONFIRMED_RSVP") {
      sheet.getRange(i + 1, 6).setValue("NO_SHOW").setBackground("#ffe4e6");
      sheet.getRange(i + 1, 7).setValue(""); // Release desk
      sweptCount++;
    }
  }

  SpreadsheetApp.getUi().alert(`15-Minute Protocol Triggered:\nMarked ${sweptCount} teams as NO_SHOW.\nDesk allocations have been liberated for the standby queue!`);
}

/**
 * Opens a sleek mobile-friendly Ground Check-in Sidebar in Google Sheets
 */
function showCheckinSidebar() {
  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
      </head>
      <body class="p-4 bg-gray-900 text-gray-100 font-sans text-xs">
        <h2 class="text-sm font-bold text-white mb-2">Ground Desk Allocator</h2>
        <p class="text-gray-400 mb-4 text-[11px]">1-click assign next available CRC hall desk.</p>
        
        <div class="mb-3">
          <label class="block text-gray-300 font-semibold mb-1">Enter Team ID or Name:</label>
          <input type="text" id="teamInput" class="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white" placeholder="e.g. 1 or NeuralForge">
        </div>
        
        <button onclick="executeCheckin()" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-3 rounded shadow">
          Check In & Allocate Desk
        </button>
        
        <div id="statusResult" class="mt-4 p-2.5 rounded bg-gray-800 text-gray-300 text-[11px] hidden"></div>

        <script>
          function executeCheckin() {
            const input = document.getElementById("teamInput").value.trim();
            if (!input) return alert("Please enter team ID or name");
            google.script.run
              .withSuccessHandler(function(res) {
                const box = document.getElementById("statusResult");
                box.classList.remove("hidden");
                box.innerHTML = res;
              })
              .processGroundCheckin(input);
          }
        </script>
      </body>
    </html>
  `).setTitle("Paradox'27 Ground Check-in");
  
  SpreadsheetApp.getUi().showSidebar(html);
}

/**
 * Server-side function called by Sidebar to allocate desk atomically in Sheet
 */
function processGroundCheckin(teamIdentifier) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const data = sheet.getDataRange().getValues();
  
  // Find team
  let targetRow = -1;
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(teamIdentifier) || String(data[i][1]).toLowerCase() === String(teamIdentifier).toLowerCase()) {
      targetRow = i + 1;
      break;
    }
  }

  if (targetRow === -1) {
    return `<span class="text-red-400">Team "${teamIdentifier}" not found in sheet.</span>`;
  }

  // Find next vacant desk
  const occupiedDesks = new Set();
  for (let i = 1; i < data.length; i++) {
    if (data[i][6]) occupiedDesks.add(String(data[i][6]));
  }

  let assignedDesk = null;
  for (let d = 1; d <= TOTAL_STANDARD_DESKS; d++) {
    const candidate = "DESK-" + (d < 10 ? "0" + d : d);
    if (!occupiedDesks.has(candidate)) {
      assignedDesk = candidate;
      break;
    }
  }

  if (!assignedDesk) {
    return `<span class="text-amber-400">Venue Full! No standard desks available.</span>`;
  }

  const now = new Date().toLocaleTimeString();
  sheet.getRange(targetRow, 6).setValue("CHECKED_IN").setBackground("#d1fae5");
  sheet.getRange(targetRow, 7).setValue(assignedDesk);
  sheet.getRange(targetRow, 9).setValue(now);

  return `<span class="text-green-400 font-bold">Success!</span><br>Assigned <strong>${assignedDesk}</strong> to ${data[targetRow - 1][1]} at ${now}.`;
}

