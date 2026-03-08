"""
🗄️ قاعدة البيانات - Database Layer (SQLite)
"""

import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager


class Database:
    def __init__(self, db_path: str = "store.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def _init_db(self):
        with self.conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id          INTEGER PRIMARY KEY,
                    username    TEXT,
                    full_name   TEXT,
                    lang        TEXT DEFAULT 'ar',
                    joined_at   TEXT DEFAULT (datetime('now')),
                    is_banned   INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS services (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_ar        TEXT NOT NULL,
                    name_en        TEXT NOT NULL,
                    description_ar TEXT,
                    description_en TEXT,
                    category       TEXT DEFAULT 'digital',
                    is_active      INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id    INTEGER REFERENCES services(id),
                    name_ar       TEXT NOT NULL,
                    name_en       TEXT NOT NULL,
                    duration_days INTEGER NOT NULL,
                    price         REAL NOT NULL,
                    extra_options TEXT DEFAULT '[]',
                    features      TEXT DEFAULT '[]',
                    is_active     INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER REFERENCES users(id),
                    plan_id     INTEGER REFERENCES plans(id),
                    amount      REAL NOT NULL,
                    currency    TEXT DEFAULT 'USDT',
                    status      TEXT DEFAULT 'pending',
                    created_at  TEXT DEFAULT (datetime('now')),
                    paid_at     TEXT
                );
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER REFERENCES users(id),
                    plan_id     INTEGER REFERENCES plans(id),
                    order_id    INTEGER REFERENCES orders(id),
                    status      TEXT DEFAULT 'active',
                    started_at  TEXT DEFAULT (datetime('now')),
                    expires_at  TEXT NOT NULL,
                    credentials TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER REFERENCES users(id),
                    message     TEXT NOT NULL,
                    reply       TEXT,
                    status      TEXT DEFAULT 'open',
                    created_at  TEXT DEFAULT (datetime('now'))
                );
            """)
            self._seed(c)

    def _seed(self, c):
        if c.execute("SELECT COUNT(*) FROM services").fetchone()[0] > 0:
            return
        # خدمات تجريبية
        for svc in [
            ("نتفليكس", "Netflix", "🎬 اشتراك نتفليكس 4K حساب خاص", "🎬 Netflix 4K private account", "streaming"),
            ("VPN احترافي", "Pro VPN", "🔒 VPN سريع بأكثر من 50 سيرفر", "🔒 Fast VPN 50+ servers", "security"),
            ("بوت تلجرام", "Telegram Bot", "🤖 بوت مخصص حسب طلبك", "🤖 Custom bot on demand", "bot"),
        ]:
            c.execute("INSERT INTO services (name_ar,name_en,description_ar,description_en,category) VALUES (?,?,?,?,?)", svc)

        nf = c.execute("SELECT id FROM services WHERE name_en='Netflix'").fetchone()[0]
        vp = c.execute("SELECT id FROM services WHERE name_en='Pro VPN'").fetchone()[0]

        plans = [
            (nf, "شهر",    "1 Month",  30,  5.99,  '["جودة 4K","حساب خاص","4K Quality","Private Account"]'),
            (nf, "3 أشهر", "3 Months", 90,  14.99, '["جودة 4K","توفير 17%","Save 17%"]'),
            (nf, "سنة",    "1 Year",   365, 49.99, '["جودة 4K","أفضل قيمة","Best Value"]'),
            (vp, "شهر",    "1 Month",  30,  3.99,  '["50+ سيرفر","سرعة غير محدودة","Unlimited Speed"]'),
            (vp, "6 أشهر", "6 Months", 180, 19.99, '["50+ سيرفر","توفير 17%","Save 17%"]'),
        ]
        for p in plans:
            c.execute("INSERT INTO plans (service_id,name_ar,name_en,duration_days,price,features) VALUES (?,?,?,?,?,?)", p)

    # ——— Users ———
    def ensure_user(self, uid, username, full_name):
        with self.conn() as c:
            c.execute("""INSERT INTO users (id,username,full_name) VALUES (?,?,?)
                         ON CONFLICT(id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name""",
                      (uid, username, full_name))

    def get_user(self, uid):
        with self.conn() as c:
            r = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            return dict(r) if r else None

    def set_user_lang(self, uid, lang):
        with self.conn() as c:
            c.execute("UPDATE users SET lang=? WHERE id=?", (lang, uid))

    def get_all_users(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM users WHERE is_banned=0").fetchall()]

    # ——— Services ———
    def get_services(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM services WHERE is_active=1").fetchall()]

    def get_service(self, sid):
        with self.conn() as c:
            r = c.execute("SELECT * FROM services WHERE id=?", (sid,)).fetchone()
            return dict(r) if r else None

    def add_service(self, name_ar, name_en, desc_ar, desc_en, category):
        with self.conn() as c:
            c.execute("INSERT INTO services (name_ar,name_en,description_ar,description_en,category) VALUES (?,?,?,?,?)",
                      (name_ar, name_en, desc_ar, desc_en, category))

    # ——— Plans ———
    def get_plans(self, sid):
        with self.conn() as c:
            return [dict(r) for r in
                    c.execute("SELECT * FROM plans WHERE service_id=? AND is_active=1", (sid,)).fetchall()]

    def get_plan(self, pid):
        with self.conn() as c:
            r = c.execute("""SELECT p.*, s.name_ar as service_name_ar, s.name_en as service_name_en,
                                    s.id as service_id
                             FROM plans p JOIN services s ON p.service_id=s.id
                             WHERE p.id=?""", (pid,)).fetchone()
            return dict(r) if r else None

    def add_plan(self, sid, name_ar, name_en, days, price):
        with self.conn() as c:
            c.execute("INSERT INTO plans (service_id,name_ar,name_en,duration_days,price) VALUES (?,?,?,?,?)",
                      (sid, name_ar, name_en, days, price))

    # ——— Orders ———
    def create_order(self, uid, plan_id, amount, currency="USDT"):
        with self.conn() as c:
            c.execute("INSERT INTO orders (user_id,plan_id,amount,currency) VALUES (?,?,?,?)",
                      (uid, plan_id, amount, currency))
            return c.execute("SELECT last_insert_rowid()").fetchone()[0]

    def update_order_status(self, order_id, status):
        with self.conn() as c:
            c.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))

    def complete_order(self, order_id):
        with self.conn() as c:
            c.execute("UPDATE orders SET status='paid', paid_at=datetime('now') WHERE id=?", (order_id,))
            r = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            return dict(r) if r else None

    def get_order(self, order_id):
        with self.conn() as c:
            r = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            return dict(r) if r else None

    def get_pending_orders(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("""
                SELECT o.*, u.full_name, u.username, p.name_ar, p.name_en, p.id as plan_id
                FROM orders o
                JOIN users u ON o.user_id=u.id
                JOIN plans p ON o.plan_id=p.id
                WHERE o.status='awaiting_approval'
                ORDER BY o.created_at DESC""").fetchall()]

    def get_user_orders(self, uid):
        with self.conn() as c:
            return [dict(r) for r in c.execute("""
                SELECT o.*, p.name_ar, s.name_ar as svc_ar
                FROM orders o
                JOIN plans p ON o.plan_id=p.id
                JOIN services s ON p.service_id=s.id
                WHERE o.user_id=? ORDER BY o.created_at DESC LIMIT 10""", (uid,)).fetchall()]

    # ——— Subscriptions ———
    def create_subscription(self, uid, plan_id, order_id, days, credentials="{}"):
        expires = (datetime.now() + timedelta(days=days)).isoformat()
        with self.conn() as c:
            c.execute("""INSERT INTO subscriptions (user_id,plan_id,order_id,expires_at,credentials)
                         VALUES (?,?,?,?,?)""", (uid, plan_id, order_id, expires, credentials))

    def get_active_subscription(self, uid):
        with self.conn() as c:
            r = c.execute("""
                SELECT sub.*, p.name_ar as plan_name, p.name_en as plan_name_en,
                       s.name_ar as service_ar, s.name_en as service_en
                FROM subscriptions sub
                JOIN plans p ON sub.plan_id=p.id
                JOIN services s ON p.service_id=s.id
                WHERE sub.user_id=? AND sub.status='active' AND sub.expires_at > datetime('now')
                ORDER BY sub.expires_at DESC LIMIT 1""", (uid,)).fetchone()
            return dict(r) if r else None

    def get_all_subscriptions(self, uid):
        with self.conn() as c:
            return [dict(r) for r in c.execute("""
                SELECT sub.*, p.name_ar as plan_name, s.name_ar as service_ar
                FROM subscriptions sub
                JOIN plans p ON sub.plan_id=p.id
                JOIN services s ON p.service_id=s.id
                WHERE sub.user_id=? ORDER BY sub.started_at DESC""", (uid,)).fetchall()]

    def get_expiring_soon(self, days=3):
        threshold = (datetime.now() + timedelta(days=days)).isoformat()
        with self.conn() as c:
            return [dict(r) for r in c.execute("""
                SELECT sub.*, u.id as user_id, p.name_ar as plan_name
                FROM subscriptions sub
                JOIN users u ON sub.user_id=u.id
                JOIN plans p ON sub.plan_id=p.id
                WHERE sub.status='active' AND sub.expires_at <= ? AND sub.expires_at > datetime('now')
            """, (threshold,)).fetchall()]

    def update_subscription_credentials(self, sub_id, credentials: dict):
        with self.conn() as c:
            c.execute("UPDATE subscriptions SET credentials=? WHERE id=?",
                      (json.dumps(credentials), sub_id))

    # ——— Tickets ———
    def create_ticket(self, uid, message):
        with self.conn() as c:
            c.execute("INSERT INTO tickets (user_id,message) VALUES (?,?)", (uid, message))
            return c.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_open_tickets(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("""
                SELECT t.*, u.full_name, u.username
                FROM tickets t JOIN users u ON t.user_id=u.id
                WHERE t.status='open' ORDER BY t.created_at DESC""").fetchall()]

    def reply_ticket(self, ticket_id, reply):
        with self.conn() as c:
            c.execute("UPDATE tickets SET reply=?, status='closed' WHERE id=?", (reply, ticket_id))
            r = c.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            return dict(r) if r else None

    # ——— Stats ———
    def get_stats(self):
        with self.conn() as c:
            return {
                "total_users":   c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                "active_subs":   c.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active' AND expires_at > datetime('now')").fetchone()[0],
                "total_revenue": round(c.execute("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='paid'").fetchone()[0], 2),
                "pending_orders":c.execute("SELECT COUNT(*) FROM orders WHERE status='awaiting_approval'").fetchone()[0],
                "open_tickets":  c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0],
            }

    # ——— دوال إضافية للأدمن Wizard ———

    def add_plan_full(self, svc_id, name_ar, name_en, days, price, features=None, options=None):
        import json
        with self.conn() as c:
            c.execute("""INSERT INTO plans (service_id,name_ar,name_en,duration_days,price,features,extra_options)
                         VALUES (?,?,?,?,?,?,?)""",
                      (svc_id, name_ar, name_en, days, price,
                       json.dumps(features or []),
                       json.dumps(options or [])))

    def toggle_service(self, svc_id, active: int):
        with self.conn() as c:
            c.execute("UPDATE services SET is_active=? WHERE id=?", (active, svc_id))

    def update_service_field(self, svc_id, field, value):
        allowed = {"name_ar", "name_en", "description_ar", "description_en", "category"}
        if field not in allowed:
            return
        with self.conn() as c:
            c.execute(f"UPDATE services SET {field}=? WHERE id=?", (value, svc_id))

    def delete_service(self, svc_id):
        with self.conn() as c:
            c.execute("UPDATE services SET is_active=0 WHERE id=?", (svc_id,))

    def delete_plan(self, plan_id):
        with self.conn() as c:
            c.execute("UPDATE plans SET is_active=0 WHERE id=?", (plan_id,))

    def get_plan_options(self, plan_id):
        import json
        with self.conn() as c:
            r = c.execute("SELECT extra_options FROM plans WHERE id=?", (plan_id,)).fetchone()
            if r:
                return json.loads(r[0] or "[]")
            return []

