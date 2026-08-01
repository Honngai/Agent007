import sqlite3
import secrets
from time import time
from flask import Flask, request, session, redirect, render_template_string, jsonify
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

COURTS = {
    "Court 1": "Chara1",
    "Court 2": "Chara2",
    "Court 3": "Chara3",
}

COURT_IMAGES = {
    "Court 1": "court1.jpg",
    "Court 2": "court2.jpg",
    "Court 3": "court3.jpg",
}

YOUR_PHONE = "916009041427"
ADMIN_PATH = "court-manager-x9k2"
DB_PATH = "bookings.db"
failed_attempts = {}
BOOKING_WINDOW_DAYS = 14  # total selectable days including today (keep as a multiple of 7 for clean paging)

IST = ZoneInfo("Asia/Kolkata")


def now_ist():
    return datetime.now(IST)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            court TEXT NOT NULL,
            date TEXT NOT NULL,
            hour INTEGER NOT NULL,
            guest_name TEXT,
            UNIQUE(court, date, hour)
        )
    """)
    conn.commit()
    conn.close()


init_db()


def get_bookings(court, date_str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hour, guest_name FROM bookings WHERE court=? AND date=?", (court, date_str))
    rows = c.fetchall()
    conn.close()
    return {hour: name for hour, name in rows}


def set_booking(court, date_str, hour, guest_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if guest_name:
        c.execute("""
            INSERT INTO bookings (court, date, hour, guest_name) VALUES (?, ?, ?, ?)
            ON CONFLICT(court, date, hour) DO UPDATE SET guest_name=excluded.guest_name
        """, (court, date_str, hour, guest_name))
    else:
        c.execute("DELETE FROM bookings WHERE court=? AND date=? AND hour=?", (court, date_str, hour))
    conn.commit()
    conn.close()


HOURS = list(range(4, 23))


def format_hour(h):
    period = "AM" if h < 12 else "PM"
    display_h = h if h <= 12 else h - 12
    if display_h == 0:
        display_h = 12
    return f"{display_h}:00 {period}"


def format_date_nice(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.strftime("%B %d, %Y")


BASE_STYLE = """
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }

    body {
        background: #0d0d12;
        font-family: -apple-system, 'Segoe UI', Arial, sans-serif;
        color: #fff;
        min-height: 100vh;
        padding-bottom: 30px;
    }

    .app-container { max-width: 480px; margin: auto; }

    .topbar {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 20px 20px 16px;
    }
    .topbar .app-title {
        font-size: 17px;
        font-weight: 700;
        color: #fff;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .detail-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 18px 20px 14px;
    }
    .back-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #fff;
        text-decoration: none;
        font-size: 14px;
        font-weight: 600;
    }
    .detail-court-title { font-size: 17px; font-weight: 700; color: #fff; }
    .calendar-icon-btn {
        width: 32px; height: 32px;
        border-radius: 8px;
        background: rgba(236,72,153,0.15);
        display: flex; align-items: center; justify-content: center;
        color: #ec4899;
        font-size: 16px;
    }

    /* Hero */
    .hero {
        position: relative;
        margin: 0 20px 24px;
        border-radius: 20px;
        overflow: hidden;
        height: 220px;
        background-image: url('/static/hero-banner.jpg');
        background-size: cover;
        background-position: center;
    }
    .hero::after {
        content: "";
        position: absolute; inset: 0;
        background: linear-gradient(180deg, rgba(13,13,18,0.1) 0%, rgba(13,13,18,0.85) 100%);
    }
    .hero-content { position: absolute; bottom: 20px; left: 20px; right: 20px; z-index: 2; }
    .hero-greeting { font-size: 14px; color: #ddd; margin-bottom: 4px; }
    .hero-title { font-size: 26px; font-weight: 800; line-height: 1.2; }
    .hero-title .accent { color: #ec4899; }
    .hero-sub { font-size: 13px; color: #bbb; margin-top: 8px; line-height: 1.4; }

    .section-title { font-size: 15px; font-weight: 700; color: #fff; margin: 0 20px 14px; }

    .court-list { padding: 0 20px; display: flex; flex-direction: column; gap: 14px; }
    .court-card {
        display: block; text-decoration: none; position: relative;
        border-radius: 16px; overflow: hidden; height: 110px;
        background-size: cover;
        background-position: center;
    }
    .court-card::before {
        content: ""; position: absolute; inset: 0;
        background: linear-gradient(90deg, rgba(13,13,18,0.15) 0%, rgba(13,13,18,0.75) 60%, rgba(13,13,18,0.9) 100%);
    }
    .court-card-content {
        position: absolute; inset: 0; display: flex; align-items: center;
        padding: 0 16px; gap: 14px; z-index: 2;
    }
    .court-icon-badge {
        width: 42px; height: 42px; border-radius: 12px; background: #ec4899;
        display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0;
    }
    .court-card-text { flex: 1; }
    .court-card-name { font-size: 16px; font-weight: 700; color: #fff; }
    .court-card-sub { font-size: 12px; color: #ccc; margin-top: 2px; }
    .court-card-arrow { color: #999; font-size: 20px; }

    /* Court Detail Info Card */
    .court-info-card {
        margin: 0 20px 24px;
        border-radius: 16px;
        overflow: hidden;
        background: #17171d;
        display: flex;
        height: 130px;
    }
    .court-info-image {
        width: 42%;
        background-size: cover;
        background-position: center;
        flex-shrink: 0;
    }
    .court-info-right {
        flex: 1;
        padding: 16px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .court-info-header { display: flex; align-items: center; gap: 10px; }
    .court-info-icon {
        width: 38px; height: 38px; border-radius: 11px; background: #ec4899;
        display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0;
    }
    .court-info-name { font-size: 16px; font-weight: 700; color: #fff; }
    .court-info-sub { font-size: 11.5px; color: #999; margin-top: 1px; }

    .court-tags { display: flex; gap: 14px; margin-top: 8px; }
    .court-tag { display: flex; flex-direction: column; align-items: center; gap: 3px; }
    .court-tag-icon { font-size: 15px; color: #ccc; }
    .court-tag-label { font-size: 9.5px; color: #999; font-weight: 600; white-space: nowrap; }

    /* Date Scroller */
    .date-scroll-section { margin: 0 0 22px; }
    .date-scroll-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 20px 12px;
        gap: 10px;
    }
    .date-scroll-label { font-size: 15px; font-weight: 700; color: #fff; }
    .date-scroll-nav { display: flex; gap: 8px; flex-shrink: 0; }
    .week-nav-btn {
        background: #17171d;
        color: #fff;
        border: none;
        border-radius: 10px;
        padding: 7px 14px;
        font-size: 12px;
        font-weight: 700;
        cursor: pointer;
        white-space: nowrap;
    }
    .week-nav-btn.next { background: #ec4899; }
    .week-nav-btn:disabled { opacity: 0.3; cursor: default; }

    .date-scroll-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 0 20px;
        overflow-x: auto;
        scrollbar-width: none;
    }
    .date-scroll-row::-webkit-scrollbar { display: none; }
    .day-card {
        flex-shrink: 0;
        width: 62px;
        height: 68px;
        border-radius: 14px;
        background: #17171d;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 2px;
        cursor: pointer;
        border: none;
        color: #fff;
    }
    .day-card.active { background: #ec4899; }
    .day-card .day-name { font-size: 11px; font-weight: 600; color: inherit; opacity: 0.8; }
    .day-card .day-num { font-size: 19px; font-weight: 800; color: inherit; }
    .day-card .day-month { font-size: 9.5px; font-weight: 600; color: inherit; opacity: 0.7; text-transform: uppercase; }

    /* Slots Section */
    .slots-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 20px 14px;
    }
    .slots-title { font-size: 15px; font-weight: 700; color: #fff; }
    .legend { display: flex; gap: 14px; font-size: 11.5px; color: #999; }
    .legend-item { display: flex; align-items: center; gap: 5px; }
    .dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
    .dot-available { background: #4ade80; }
    .dot-booked { background: #666; }

    .slots-list { padding: 0 20px; display: flex; flex-direction: column; gap: 10px; }
    .slot-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #17171d;
        border-radius: 12px;
        padding: 14px 16px;
    }
    .slot-time { font-size: 13.5px; font-weight: 600; color: #fff; flex: 1.1; }
    .slot-status { display: flex; align-items: center; gap: 6px; font-size: 12.5px; flex: 1; }
    .slot-status.available { color: #4ade80; }
    .slot-status.booked { color: #888; }

    .book-btn {
        padding: 9px 18px;
        border-radius: 10px;
        border: none;
        font-size: 12.5px;
        font-weight: 700;
        cursor: pointer;
        text-decoration: none;
        white-space: nowrap;
    }
    .book-btn.available { background: #ec4899; color: white; }
    .book-btn.booked { background: #2a2a32; color: #666; cursor: default; }

    .loading-spinner { text-align: center; padding: 40px; color: #777; font-size: 14px; }

    .footer-note {
        margin: 20px 20px 0;
        background: #17171d;
        border-radius: 14px;
        padding: 16px;
        display: flex;
        align-items: flex-start;
        gap: 12px;
    }
    .footer-note-icon {
        width: 36px; height: 36px; border-radius: 10px; background: #ec4899;
        display: flex; align-items: center; justify-content: center; font-size: 15px; flex-shrink: 0;
    }
    .footer-note-title { font-size: 13px; font-weight: 700; color: #fff; }
    .footer-note-sub { font-size: 11.5px; color: #999; margin-top: 2px; line-height: 1.4; }

    /* Admin */
    .logout-bar { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; }
    .logout-bar a { color: #f87171; font-size: 13px; text-decoration: none; font-weight: 600; }
    .admin-court-name { font-weight: 700; color: #fff; font-size: 14px; }

    input[type=text].name-input {
        padding: 8px 10px; border-radius: 8px; border: 1px solid #333;
        width: 90px; font-size: 12px; background: #1a1a22; color: #fff;
    }
    .save-btn {
        background: #22c55e; padding: 8px 12px; border-radius: 8px; border: none;
        color: white; cursor: pointer; font-size: 11px; font-weight: 700;
    }
    .admin-slot-row { display: flex; align-items: center; justify-content: space-between; background: #17171d; border-radius: 12px; padding: 12px 16px; margin-bottom: 8px; }
    .admin-form-inline { display: flex; align-items: center; gap: 6px; }

    .login-wrapper { display: flex; justify-content: center; align-items: center; min-height: 60vh; padding: 20px; }
    .login-box { text-align: center; width: 100%; }
    .login-box select, .login-box input[type=password] {
        padding: 14px 16px; font-size: 15px; border-radius: 12px; border: 1px solid #2a2a35;
        width: 100%; max-width: 280px; margin-bottom: 12px; display: block;
        margin-left: auto; margin-right: auto; background: #1a1a22; color: #fff;
    }
    .login-box button {
        display: block; margin: 10px auto 0; padding: 14px 30px; background: #ec4899;
        color: white; border: none; border-radius: 12px; cursor: pointer;
        font-size: 15px; font-weight: 700; width: 100%; max-width: 280px;
    }
    .error { color: #f87171; font-size: 13px; margin-top: 12px; }
    .login-title { font-size: 22px; font-weight: 800; margin-bottom: 6px; }
    .login-sub { font-size: 13px; color: #999; margin-bottom: 28px; }

    .admin-date-picker { position: relative; background: #17171d; border-radius: 12px; padding: 12px 16px; margin: 0 20px 18px; }
    .admin-date-picker input[type=date] { position: absolute; inset: 0; opacity: 0; width: 100%; height: 100%; cursor: pointer; }
</style>
"""

LANDING_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0d0d12">
<title>Pickleball Court Booking</title>
{{ style|safe }}
</head>
<body>
<div class="app-container">
    <div class="topbar">
        <span class="app-title">🏓 Pickleball Court Booking</span>
    </div>

    <div class="hero">
        <div class="hero-content">
            <div class="hero-greeting">Hi there! 👋</div>
            <div class="hero-title">Book Your<br><span class="accent">Pickleball Court</span></div>
            <div class="hero-sub">Choose a court below to<br>check availability &amp; book your slot.</div>
        </div>
    </div>

    <div class="section-title">Select a Court</div>
    <div class="court-list">
        {% for c in courts %}
            <a class="court-card" style="background-image: url('/static/{{ court_images[c] }}');" href="/booking?court={{ c|urlencode }}">
                <div class="court-card-content">
                    <div class="court-icon-badge">🏓</div>
                    <div class="court-card-text">
                        <div class="court-card-name">{{ c }}</div>
                        <div class="court-card-sub">Outdoor Court</div>
                    </div>
                    <div class="court-card-arrow">›</div>
                </div>
            </a>
        {% endfor %}
    </div>
</div>
</body>
</html>
"""

GUEST_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0d0d12">
<title>{{ selected_court }} — Booking</title>
{{ style|safe }}
</head>
<body>
<div class="app-container">
    <div class="detail-topbar">
        <a class="back-btn" href="/">&larr; Back to Courts</a>
        <span class="detail-court-title">{{ selected_court }}</span>
        <label class="calendar-icon-btn" style="position:relative; cursor:pointer;">
            📅
            <input type="date" id="calendarPicker"
                   style="position:absolute; inset:0; opacity:0; width:100%; height:100%; cursor:pointer;"
                   value="{{ selected_date }}">
        </label>
    </div>

    <div class="court-info-card">
        <div class="court-info-image" style="background-image: url('/static/{{ court_image }}');"></div>
        <div class="court-info-right">
            <div class="court-info-header">
                <div class="court-info-icon">🏓</div>
                <div>
                    <div class="court-info-name">{{ selected_court }}</div>
                    <div class="court-info-sub">Outdoor Court</div>
                </div>
            </div>
            <div class="court-tags">
                <div class="court-tag">
                    <div class="court-tag-icon">☀️</div>
                    <div class="court-tag-label">Outdoor</div>
                </div>
                <div class="court-tag">
                    <div class="court-tag-icon">👥</div>
                    <div class="court-tag-label">4 Players</div>
                </div>
                <div class="court-tag">
                    <div class="court-tag-icon">🎾</div>
                    <div class="court-tag-label">Hard Surface</div>
                </div>
            </div>
        </div>
    </div>

    <div class="date-scroll-section">
        <div class="date-scroll-header">
            <div class="date-scroll-label">Select Date</div>
            <div class="date-scroll-nav">
                <button type="button" id="prevWeekBtn" class="week-nav-btn">&lsaquo; Prev</button>
                <button type="button" id="nextWeekBtn" class="week-nav-btn next">Next &rsaquo;</button>
            </div>
        </div>
        <div class="date-scroll-row" id="dateScrollRow"></div>
    </div>

    <div class="slots-header">
        <span class="slots-title">Available Time Slots</span>
        <div class="legend">
            <span class="legend-item"><span class="dot dot-available"></span>Available</span>
            <span class="legend-item"><span class="dot dot-booked"></span>Booked</span>
        </div>
    </div>

    <div class="slots-list" id="slotsContainer">
        <div class="loading-spinner">Loading...</div>
    </div>

    <div class="footer-note">
        <div class="footer-note-icon">📅</div>
        <div>
            <div class="footer-note-title">All times are in your local time</div>
            <div class="footer-note-sub">Bookings can be made up to {{ booking_window }} days in advance.</div>
        </div>
    </div>
</div>

<script>
    const phone = "{{ phone }}";
    const currentCourt = "{{ selected_court }}";
    const bookingWindowDays = {{ booking_window }};
    const serverToday = "{{ today }}"; // IST date from server, authoritative
    let currentDate = "{{ selected_date }}";
    let pageOffset = 0; // how many days ahead of serverToday the current page of 7 cards starts

    function waMessage(court, dateStr, hourLabel) {
        const msg = `Hi! I'd like to book ${court} on ${dateStr} at ${hourLabel}. Please confirm availability.`;
        return encodeURIComponent(msg);
    }

    function toDateStr(d) {
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }

    function getServerTodayDate() {
        const [y, m, d] = serverToday.split('-').map(Number);
        return new Date(y, m - 1, d);
    }

    function diffDaysFromToday(dateStr) {
        const [y, m, d] = dateStr.split('-').map(Number);
        const target = new Date(y, m - 1, d);
        const today = getServerTodayDate();
        return Math.round((target - today) / 86400000);
    }

    function clampPageOffset(offset) {
        const maxOffset = Math.max(0, Math.floor((bookingWindowDays - 1) / 7) * 7);
        return Math.min(Math.max(offset, 0), maxOffset);
    }

    function buildDateCards() {
        const row = document.getElementById('dateScrollRow');
        row.innerHTML = '';

        const today = getServerTodayDate();

        for (let i = 0; i < 7; i++) {
            const dayNum = pageOffset + i;
            if (dayNum > bookingWindowDays - 1) break;

            const dt = new Date(today);
            dt.setDate(today.getDate() + dayNum);
            const dateStr = toDateStr(dt);

            const card = document.createElement('button');
            card.className = 'day-card' + (dateStr === currentDate ? ' active' : '');
            card.innerHTML = `
                <span class="day-name">${dt.toLocaleDateString('en-US', {weekday: 'short'})}</span>
                <span class="day-num">${dt.getDate().toString().padStart(2,'0')}</span>
                <span class="day-month">${dt.toLocaleDateString('en-US', {month: 'short'})}</span>
            `;
            card.addEventListener('click', () => {
                currentDate = dateStr;
                document.getElementById('calendarPicker').value = dateStr;
                buildDateCards();
                loadSlots();
            });
            row.appendChild(card);
        }

        updateNavButtons();
    }

    function updateNavButtons() {
        const prevBtn = document.getElementById('prevWeekBtn');
        const nextBtn = document.getElementById('nextWeekBtn');
        prevBtn.disabled = pageOffset <= 0;
        nextBtn.disabled = pageOffset + 7 > bookingWindowDays - 1;
    }

    async function loadSlots() {
        const container = document.getElementById('slotsContainer');
        container.innerHTML = '<div class="loading-spinner">Loading...</div>';

        try {
            const res = await fetch(`/api/slots?court=${encodeURIComponent(currentCourt)}&date=${currentDate}`);
            const data = await res.json();

            if (!data.slots || data.slots.length === 0) {
                container.innerHTML = '<div class="loading-spinner">No slots available for this date.</div>';
                return;
            }

            let html = '';
            data.slots.forEach(slot => {
                if (slot.booked) {
                    html += `<div class="slot-row">
                        <div class="slot-time">${slot.time_label}</div>
                        <div class="slot-status booked"><span class="dot dot-booked"></span>Booked</div>
                        <button class="book-btn booked" disabled>Booked</button>
                    </div>`;
                } else {
                    const waLink = `https://wa.me/${phone}?text=${waMessage(currentCourt, data.nice_date, slot.time_label)}`;
                    html += `<div class="slot-row">
                        <div class="slot-time">${slot.time_label}</div>
                        <div class="slot-status available"><span class="dot dot-available"></span>Available</div>
                        <a class="book-btn available" href="${waLink}" target="_blank">Book Now</a>
                    </div>`;
                }
            });

            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = '<div class="loading-spinner">Error loading slots.</div>';
        }
    }

    document.getElementById('prevWeekBtn').addEventListener('click', () => {
        pageOffset = clampPageOffset(pageOffset - 7);
        const today = getServerTodayDate();
        const dt = new Date(today);
        dt.setDate(today.getDate() + pageOffset);
        currentDate = toDateStr(dt);
        document.getElementById('calendarPicker').value = currentDate;
        buildDateCards();
        loadSlots();
    });

    document.getElementById('nextWeekBtn').addEventListener('click', () => {
        pageOffset = clampPageOffset(pageOffset + 7);
        const today = getServerTodayDate();
        const dt = new Date(today);
        dt.setDate(today.getDate() + pageOffset);
        currentDate = toDateStr(dt);
        document.getElementById('calendarPicker').value = currentDate;
        buildDateCards();
        loadSlots();
    });

    // Calendar icon picker — jump straight to any date within the window
    const calendarPicker = document.getElementById('calendarPicker');
    calendarPicker.min = serverToday;
    const maxD = getServerTodayDate();
    maxD.setDate(maxD.getDate() + (bookingWindowDays - 1));
    calendarPicker.max = toDateStr(maxD);

    calendarPicker.addEventListener('change', () => {
        if (calendarPicker.value) {
            currentDate = calendarPicker.value;
            const diff = diffDaysFromToday(currentDate);
            pageOffset = clampPageOffset(Math.floor(diff / 7) * 7);
            buildDateCards();
            loadSlots();
        }
    });

    // Initialize page based on the initially selected date
    pageOffset = clampPageOffset(Math.floor(diffDaysFromToday(currentDate) / 7) * 7);
    buildDateCards();
    loadSlots();
</script>
</body>
</html>
"""

ADMIN_LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<title>Admin Login</title>
{{ style|safe }}
</head>
<body>
<div class="app-container">
    <div class="login-wrapper">
        <div class="login-box">
            <div class="login-title">🔐 Admin Login</div>
            <div class="login-sub">Select court &amp; enter password</div>
            <form method="POST">
                <select name="court" required>
                    {% for c in courts %}
                        <option value="{{ c }}">{{ c }}</option>
                    {% endfor %}
                </select>
                <input type="password" name="password" placeholder="Enter password" required>
                <button type="submit">Login</button>
            </form>
            {% if error %}<div class="error">{{ error }}</div>{% endif %}
        </div>
    </div>
</div>
</body>
</html>
"""

ADMIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="manifest" href="/static/manifest.json">
<title>Admin - Manage Bookings</title>
{{ style|safe }}
</head>
<body>
<div class="app-container">
    <div class="topbar"><span class="app-title">🏓 Manage {{ court }}</span></div>
    <div class="logout-bar">
        <span class="admin-court-name">Managing: {{ court }}</span>
        <a href="/{{ admin_path }}/logout">Logout</a>
    </div>

    <div class="admin-date-picker">
        <form method="GET">
            📅 {{ nice_date }}
            <input type="date" name="date" value="{{ selected_date }}" onchange="this.form.submit()">
        </form>
    </div>

    <div class="slots-list" style="padding:0 20px;">
        {% for hour in hours %}
            {% set current_name = bookings.get(hour, "") %}
            <div class="admin-slot-row">
                <div class="slot-time">{{ format_hour(hour) }} – {{ format_hour(hour+1) }}</div>
                <div class="slot-status {{ 'booked' if current_name else 'available' }}">
                    <span class="dot {{ 'dot-booked' if current_name else 'dot-available' }}"></span>
                    {{ 'Booked' if current_name else 'Available' }}
                </div>
                <form class="admin-form-inline" method="POST" action="/{{ admin_path }}/toggle">
                    <input type="hidden" name="date" value="{{ selected_date }}">
                    <input type="hidden" name="hour" value="{{ hour }}">
                    <input type="text" class="name-input" name="guest_name" placeholder="Name" value="{{ current_name }}">
                    <button type="submit" class="save-btn">Save</button>
                </form>
            </div>
        {% endfor %}
    </div>
</div>
</body>
</html>
"""


@app.route("/")
def landing_page():
    court_list = list(COURTS.keys())
    return render_template_string(LANDING_PAGE, style=BASE_STYLE, courts=court_list, court_images=COURT_IMAGES)


@app.route("/booking")
def guest_view():
    court_list = list(COURTS.keys())
    selected_court = request.args.get("court") or court_list[0]
    if selected_court not in COURTS:
        selected_court = court_list[0]

    today_ist = now_ist().strftime("%Y-%m-%d")
    selected_date = request.args.get("date") or today_ist

    return render_template_string(
        GUEST_PAGE,
        style=BASE_STYLE,
        courts=court_list,
        selected_court=selected_court,
        selected_date=selected_date,
        today=today_ist,
        phone=YOUR_PHONE,
        booking_window=BOOKING_WINDOW_DAYS,
        court_image=COURT_IMAGES.get(selected_court, "court1.jpg"),
    )


@app.route("/api/slots")
def api_slots():
    court = request.args.get("court")
    date_str = request.args.get("date")

    if court not in COURTS:
        return jsonify({"error": "Invalid court"}), 400

    now = now_ist()
    today_str = now.strftime("%Y-%m-%d")
    max_date_str = (now.date() + timedelta(days=BOOKING_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")

    # Outside the allowed booking window (past or too far in future)
    if date_str < today_str or date_str > max_date_str:
        return jsonify({
            "court": court,
            "date": date_str,
            "nice_date": format_date_nice(date_str),
            "slots": []
        })

    bookings = get_bookings(court, date_str)

    slots = []
    for hour in HOURS:
        # If it's today (IST), skip hours that have already started/passed
        if date_str == today_str and hour < now.hour:
            continue
        slots.append({
            "hour": hour,
            "time_label": f"{format_hour(hour)} – {format_hour(hour+1)}",
            "booked": hour in bookings
        })

    return jsonify({
        "court": court,
        "date": date_str,
        "nice_date": format_date_nice(date_str),
        "slots": slots
    })


@app.route(f"/{ADMIN_PATH}", methods=["GET"])
def admin_view():
    admin_court = session.get("admin_court")
    if not admin_court or admin_court not in COURTS:
        return render_template_string(ADMIN_LOGIN_PAGE, style=BASE_STYLE, courts=list(COURTS.keys()), error=None)

    selected_date = request.args.get("date") or now_ist().strftime("%Y-%m-%d")
    bookings = get_bookings(admin_court, selected_date)

    return render_template_string(
        ADMIN_PAGE,
        style=BASE_STYLE,
        court=admin_court,
        selected_date=selected_date,
        nice_date=format_date_nice(selected_date),
        hours=HOURS,
        bookings=bookings,
        format_hour=format_hour,
        admin_path=ADMIN_PATH
    )


@app.route(f"/{ADMIN_PATH}", methods=["POST"])
def admin_login():
    ip = request.remote_addr
    now = time()

    if ip in failed_attempts and now - failed_attempts[ip]["time"] > 300:
        failed_attempts[ip] = {"count": 0, "time": now}

    attempts = failed_attempts.get(ip, {"count": 0, "time": now})

    if attempts["count"] >= 5:
        return render_template_string(ADMIN_LOGIN_PAGE, style=BASE_STYLE, courts=list(COURTS.keys()),
                                        error="Too many attempts. Try again in 5 minutes.")

    court = request.form.get("court", "")
    password = request.form.get("password", "")

    if court in COURTS and password == COURTS[court]:
        failed_attempts.pop(ip, None)
        session["admin_court"] = court
        return redirect(f"/{ADMIN_PATH}")

    failed_attempts[ip] = {"count": attempts["count"] + 1, "time": now}
    return render_template_string(ADMIN_LOGIN_PAGE, style=BASE_STYLE, courts=list(COURTS.keys()),
                                    error="Wrong court or password.")


@app.route(f"/{ADMIN_PATH}/logout")
def admin_logout():
    session.pop("admin_court", None)
    return redirect("/")


@app.route(f"/{ADMIN_PATH}/toggle", methods=["POST"])
def admin_toggle():
    admin_court = session.get("admin_court")
    if not admin_court:
        return redirect(f"/{ADMIN_PATH}")

    date_str = request.form.get("date")
    hour = int(request.form.get("hour"))
    guest_name = request.form.get("guest_name", "").strip()

    set_booking(admin_court, date_str, hour, guest_name)

    return redirect(f"/{ADMIN_PATH}?date={date_str}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
