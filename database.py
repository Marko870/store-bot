"""
🗄️ قاعدة البيانات - PostgreSQL
"""
import json
import psycopg
import psycopg as psycopg2
from psycopg.rows import dict_row
from datetime import datetime, timedelta
from contextlib import contextmanager
from config import Config

cfg = Config()


class Database:
    def __init__(self):
        self._init_db()

    @contextmanager
    def conn(self):
        c = psycopg2.connect(cfg.DATABASE_URL)
        c.autocommit = False
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def fetch(self, sql, params=()):
        with self.conn() as c:
            cur = c.cursor(row_factory=dict_row)
            cur.execute(sql, params)
            return cur.fetchall()

    def fetchone(self, sql, params=()):
        with self.conn() as c:
            cur = c.cursor(row_factory=dict_row)
            cur.execute(sql, params)
            return cur.fetchone()

    def execute(self, sql, params=()):
        with self.conn() as c:
            cur = c.cursor()
            cur.execute(sql, params)
            return cur

    def execute_returning(self, sql, params=()):
        with self.conn() as c:
            cur = c.cursor()
            cur.execute(sql, params)
            c.commit()
            return cur.fetchone()[0]

    def _init_db(self):
        with self.conn() as c:
            cur = c.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id          BIGINT PRIMARY KEY,
                    username    TEXT,
                    full_name   TEXT,
                    lang        TEXT DEFAULT 'ar',
                    country     TEXT DEFAULT '',
                    state       TEXT DEFAULT NULL,
                    joined_at   TIMESTAMP DEFAULT NOW(),
                    is_banned   INTEGER DEFAULT 0
                );
                -- إضافة أعمدة جديدة لو ما موجودة (للقواعد القديمة)
                DO $$ BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS state TEXT DEFAULT NULL;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
                DO $$ BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS flow TEXT DEFAULT NULL;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;

                CREATE TABLE IF NOT EXISTS service_types (
                    id          SERIAL PRIMARY KEY,
                    name        TEXT UNIQUE NOT NULL,
                    label_ar    TEXT NOT NULL,
                    label_en    TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS services (
                    id             SERIAL PRIMARY KEY,
                    name_ar        TEXT NOT NULL,
                    name_en        TEXT NOT NULL,
                    description_ar TEXT DEFAULT '',
                    description_en TEXT DEFAULT '',
                    type_id        INTEGER REFERENCES service_types(id),
                    category       TEXT DEFAULT 'digital',
                    min_amount     REAL DEFAULT 0,
                    max_amount     REAL DEFAULT 0,
                    daily_limit    INTEGER DEFAULT 0,
                    is_active      INTEGER DEFAULT 1
                );
                DO $$ BEGIN
                    ALTER TABLE services ADD COLUMN IF NOT EXISTS max_amount REAL DEFAULT 0;
                EXCEPTION WHEN duplicate_column THEN NULL; END $$;
                DO $$ BEGIN
                    ALTER TABLE services ADD COLUMN IF NOT EXISTS daily_limit INTEGER DEFAULT 0;
                EXCEPTION WHEN duplicate_column THEN NULL; END $$;

                CREATE TABLE IF NOT EXISTS service_variants (
                    id            SERIAL PRIMARY KEY,
                    service_id    INTEGER REFERENCES services(id) ON DELETE CASCADE,
                    name_ar       TEXT NOT NULL,
                    name_en       TEXT NOT NULL,
                    extra_options TEXT DEFAULT '[]',
                    is_active     INTEGER DEFAULT 1
                );
                DO $$ BEGIN
                    ALTER TABLE service_variants ADD COLUMN IF NOT EXISTS extra_options TEXT DEFAULT '[]';
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
                DO $$ BEGIN
                    ALTER TABLE plans ADD COLUMN IF NOT EXISTS variant_id INTEGER REFERENCES service_variants(id) ON DELETE SET NULL;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;

                CREATE TABLE IF NOT EXISTS plans (
                    id            SERIAL PRIMARY KEY,
                    service_id    INTEGER REFERENCES services(id),
                    variant_id    INTEGER REFERENCES service_variants(id) ON DELETE SET NULL,
                    name_ar       TEXT NOT NULL,
                    name_en       TEXT NOT NULL,
                    duration_days INTEGER DEFAULT 0,
                    price         REAL NOT NULL,
                    features      TEXT DEFAULT '[]',
                    extra_options TEXT DEFAULT '[]',
                    is_active     INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS exchange_rates (
                    id         SERIAL PRIMARY KEY,
                    service_id INTEGER REFERENCES services(id),
                    rate       REAL NOT NULL,
                    unit       TEXT DEFAULT 'USDT',
                    updated_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id            SERIAL PRIMARY KEY,
                    user_id       BIGINT REFERENCES users(id),
                    plan_id       INTEGER REFERENCES plans(id),
                    service_id    INTEGER REFERENCES services(id),
                    amount        REAL NOT NULL,
                    amount_local  REAL DEFAULT 0,
                    phone_number  TEXT DEFAULT '',
                    currency      TEXT DEFAULT 'USDT',
                    status        TEXT DEFAULT 'pending',
                    order_type    TEXT DEFAULT 'subscription',
                    user_options  TEXT DEFAULT '{}',
                    user_inputs   TEXT DEFAULT '{}',
                    created_at    TIMESTAMP DEFAULT NOW(),
                    paid_at       TIMESTAMP
                );
                DO $$ BEGIN
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS amount_local REAL DEFAULT 0;
                EXCEPTION WHEN duplicate_column THEN NULL; END $$;
                DO $$ BEGIN
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS phone_number TEXT DEFAULT '';
                EXCEPTION WHEN duplicate_column THEN NULL; END $$;
                DO $$ BEGIN
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_type TEXT DEFAULT 'subscription';
                EXCEPTION WHEN duplicate_column THEN NULL; END $$;

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id          SERIAL PRIMARY KEY,
                    user_id     BIGINT REFERENCES users(id),
                    plan_id     INTEGER REFERENCES plans(id),
                    order_id    INTEGER REFERENCES orders(id),
                    service_id  INTEGER REFERENCES services(id),
                    status      TEXT DEFAULT 'active',
                    started_at  TIMESTAMP DEFAULT NOW(),
                    expires_at  TIMESTAMP,
                    credentials TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    id          SERIAL PRIMARY KEY,
                    user_id     BIGINT REFERENCES users(id),
                    message     TEXT NOT NULL,
                    reply       TEXT,
                    status      TEXT DEFAULT 'open',
                    created_at  TIMESTAMP DEFAULT NOW()
                );
            """)
            self._seed(cur)

    def _seed(self, cur):
        cur.execute("SELECT COUNT(*) FROM service_types")
        if cur.fetchone()[0] > 0:
            return
        cur.execute("""
            INSERT INTO service_types (name, label_ar, label_en) VALUES
            ('subscription', 'اشتراك رقمي',              'Digital Subscription'),
            ('recharge',     'تعبئة رصيد / سيرياتيل كاش', 'Recharge'),
            ('exchange',     'تحويل عملات',               'Currency Exchange')
        """)

    # ══════════════════════════════
    #   Users
    # ══════════════════════════════

    def ensure_user(self, uid, username, full_name):
        self.execute("""
            INSERT INTO users (id, username, full_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET username=EXCLUDED.username, full_name=EXCLUDED.full_name
        """, (uid, username, full_name))

    def ensure_user_new(self, uid, username, full_name) -> bool:
        """يرجع True لو المستخدم جديد"""
        existing = self.fetchone("SELECT id FROM users WHERE id=%s", (uid,))
        if existing:
            self.execute("""
                UPDATE users SET username=%s, full_name=%s WHERE id=%s
            """, (username, full_name, uid))
            return False
        self.execute("""
            INSERT INTO users (id, username, full_name) VALUES (%s, %s, %s)
        """, (uid, username, full_name))
        return True

    def set_user_country(self, uid, country):
        self.execute("UPDATE users SET country=%s WHERE id=%s", (country, uid))

    def set_user_state(self, uid, state):
        self.execute("UPDATE users SET state=%s WHERE id=%s", (state, uid))

    def get_user_state(self, uid):
        r = self.fetchone("SELECT state FROM users WHERE id=%s", (uid,))
        return r["state"] if r else None

    def clear_user_state(self, uid):
        self.execute("UPDATE users SET state=NULL WHERE id=%s", (uid,))

    def save_flow(self, uid, flow: dict):
        import json
        self.execute("UPDATE users SET flow=%s WHERE id=%s", (json.dumps(flow), uid))

    def get_flow(self, uid):
        import json
        r = self.fetchone("SELECT flow FROM users WHERE id=%s", (uid,))
        if r and r.get("flow"):
            try: return json.loads(r["flow"])
            except: return None
        return None

    def clear_flow(self, uid):
        self.execute("UPDATE users SET flow=NULL WHERE id=%s", (uid,))

    def get_user(self, uid):
        return self.fetchone("SELECT * FROM users WHERE id=%s", (uid,))

    def get_user_country(self, uid):
        r = self.fetchone("SELECT country FROM users WHERE id=%s", (uid,))
        return r["country"] if r else ""

    def set_user_lang(self, uid, lang):
        self.execute("UPDATE users SET lang=%s WHERE id=%s", (lang, uid))

    def get_all_users(self):
        return self.fetch("SELECT * FROM users WHERE is_banned=0")

    def ban_user(self, uid):
        self.execute("UPDATE users SET is_banned=1 WHERE id=%s", (uid,))

    def unban_user(self, uid):
        self.execute("UPDATE users SET is_banned=0 WHERE id=%s", (uid,))

    def get_users_admin(self, status="all", page=0, per_page=5, search=""):
        offset = page * per_page
        conditions = []
        params = []

        if status == "active":
            conditions.append("is_banned=0")
        elif status == "banned":
            conditions.append("is_banned=1")

        if search:
            conditions.append(
                "(username ILIKE %s OR full_name ILIKE %s OR CAST(id AS TEXT) LIKE %s)"
            )
            s = f"%{search}%"
            params += [s, s, s]

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        rows = self.fetch(f"""
            SELECT id, username, full_name, country, lang, is_banned, joined_at
            FROM users
            {where}
            ORDER BY joined_at DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])

        total_row = self.fetchone(f"SELECT COUNT(*) as c FROM users {where}", params)
        total = total_row["c"] if total_row else 0
        return rows or [], total

    def get_user_stats(self, uid):
        """Returns subscription count and order count for a user."""
        subs = self.fetchone(
            "SELECT COUNT(*) as c FROM subscriptions WHERE user_id=%s", (uid,)
        )
        orders = self.fetchone(
            "SELECT COUNT(*) as c FROM orders WHERE user_id=%s", (uid,)
        )
        active_sub = self.fetchone("""
            SELECT sub.id, p.name_ar as plan_name, s.name_ar as service_name, sub.expires_at
            FROM subscriptions sub
            JOIN plans p ON sub.plan_id = p.id
            JOIN services s ON sub.service_id = s.id
            WHERE sub.user_id=%s AND sub.status='active' AND sub.expires_at > NOW()
            ORDER BY sub.expires_at DESC LIMIT 1
        """, (uid,))
        return {
            "total_subs": subs["c"] if subs else 0,
            "total_orders": orders["c"] if orders else 0,
            "active_sub": active_sub,
        }

    # ══════════════════════════════
    #   Service Types
    # ══════════════════════════════

    def get_service_types(self):
        return self.fetch("SELECT * FROM service_types ORDER BY id")

    def get_service_type(self, tid):
        return self.fetchone("SELECT * FROM service_types WHERE id=%s", (tid,))

    # ══════════════════════════════
    #   Services
    # ══════════════════════════════

    def get_services(self):
        return self.fetch("""
            SELECT s.*, st.name as type_name, st.label_ar as type_label_ar, st.label_en as type_label_en
            FROM services s
            LEFT JOIN service_types st ON s.type_id = st.id
            WHERE s.is_active=1 ORDER BY s.id
        """)

    # ══ Recharge ══

    def get_recharge_presets(self, service_id):
        """خيارات المبالغ الجاهزة — من exchange_rates بـ unit=SYP"""
        return self.fetch(
            "SELECT * FROM exchange_rates WHERE service_id=%s AND unit='SYP' ORDER BY rate",
            (service_id,))

    def set_recharge_preset(self, service_id, amount_syp, amount_usdt):
        """يضيف أو يحدث خيار مبلغ جاهز"""
        existing = self.fetchone(
            "SELECT id FROM exchange_rates WHERE service_id=%s AND unit='SYP' AND rate=%s",
            (service_id, amount_syp))
        if existing:
            self.execute(
                "UPDATE exchange_rates SET rate=%s WHERE service_id=%s AND unit='SYP' AND id=%s",
                (amount_syp, service_id, existing["id"]))
        else:
            self.execute(
                "INSERT INTO exchange_rates (service_id, rate, unit) VALUES (%s,%s,'SYP')",
                (service_id, amount_syp))

    def get_recharge_rate(self, service_id):
        """سعر الصرف الرئيسي: كم ليرة = 1 USDT"""
        r = self.fetchone(
            "SELECT rate FROM exchange_rates WHERE service_id=%s AND unit='USDT' ORDER BY updated_at DESC LIMIT 1",
            (service_id,))
        return r["rate"] if r else None

    def get_service_limits(self, service_id):
        """الحد الأدنى والأقصى اليومي"""
        return self.fetchone(
            "SELECT min_amount, max_amount, daily_limit FROM services WHERE id=%s",
            (service_id,))

    def count_today_recharge_orders(self, user_id, service_id):
        """عدد طلبات التعبئة اليوم لهذا المستخدم"""
        r = self.fetchone("""
            SELECT COUNT(*) as cnt FROM orders
            WHERE user_id=%s AND service_id=%s AND order_type='recharge'
            AND created_at >= CURRENT_DATE
        """, (user_id, service_id))
        return r["cnt"] if r else 0

    def create_recharge_order(self, user_id, service_id, amount_usdt, amount_local, phone):
        return self.execute_returning("""
            INSERT INTO orders
                (user_id, service_id, amount, amount_local, phone_number, order_type, status)
            VALUES (%s, %s, %s, %s, %s, 'recharge', 'pending')
            RETURNING id
        """, (user_id, service_id, amount_usdt, amount_local, phone))

    def get_pending_recharge_orders(self):
        return self.fetch("""
            SELECT o.*, u.full_name, u.username,
                   s.name_ar as svc_ar
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN services s ON o.service_id = s.id
            WHERE o.order_type='recharge' AND o.status='pending'
            ORDER BY o.created_at
        """)

    def complete_recharge_order(self, order_id):
        self.execute(
            "UPDATE orders SET status='completed', paid_at=NOW() WHERE id=%s",
            (order_id,))

    def reject_recharge_order(self, order_id):
        self.execute(
            "UPDATE orders SET status='rejected' WHERE id=%s",
            (order_id,))

    def get_user_recharge_history(self, user_id, limit=10):
        return self.fetch("""
            SELECT o.*, s.name_ar as svc_ar
            FROM orders o
            JOIN services s ON o.service_id = s.id
            WHERE o.user_id=%s AND o.order_type='recharge'
            ORDER BY o.created_at DESC LIMIT %s
        """, (user_id, limit))

    def update_service_limits(self, service_id, min_amount=None, max_amount=None, daily_limit=None):
        if min_amount is not None:
            self.execute("UPDATE services SET min_amount=%s WHERE id=%s", (min_amount, service_id))
        if max_amount is not None:
            self.execute("UPDATE services SET max_amount=%s WHERE id=%s", (max_amount, service_id))
        if daily_limit is not None:
            self.execute("UPDATE services SET daily_limit=%s WHERE id=%s", (daily_limit, service_id))

        # ══ Variants ══
    def add_variant(self, service_id, name_ar, name_en, options=None) -> int:
        return self.execute_returning(
            "INSERT INTO service_variants (service_id, name_ar, name_en, extra_options) VALUES (%s,%s,%s,%s) RETURNING id",
            (service_id, name_ar, name_en, json.dumps(options or []))
        )

    def update_variant_options(self, variant_id, options):
        self.execute("UPDATE service_variants SET extra_options=%s WHERE id=%s",
                     (json.dumps(options), variant_id))

    def get_variant(self, variant_id):
        return self.fetchone("SELECT * FROM service_variants WHERE id=%s", (variant_id,))

    def get_variant_options(self, variant_id):
        r = self.fetchone("SELECT extra_options FROM service_variants WHERE id=%s", (variant_id,))
        if r and r.get("extra_options"):
            try: return json.loads(r["extra_options"])
            except: return []
        return []

    def get_variants(self, service_id):
        return self.fetch(
            "SELECT * FROM service_variants WHERE service_id=%s AND is_active=1 ORDER BY id",
            (service_id,)
        )

    def delete_variant(self, variant_id):
        self.execute("DELETE FROM service_variants WHERE id=%s", (variant_id,))

    def get_plans_by_variant(self, variant_id):
        return self.fetch(
            """SELECT p.*, s.name_ar as service_name_ar, s.name_en as service_name_en, s.id as service_id
               FROM plans p JOIN services s ON p.service_id=s.id
               WHERE p.variant_id=%s AND p.is_active=1 ORDER BY p.price""",
            (variant_id,)
        )

    def get_plans_no_variant(self, service_id):
        """خطط الخدمة بدون variant (variant_id IS NULL)"""
        return self.fetch(
            """SELECT p.*, s.name_ar as service_name_ar, s.name_en as service_name_en, s.id as service_id
               FROM plans p JOIN services s ON p.service_id=s.id
               WHERE p.service_id=%s AND p.variant_id IS NULL AND p.is_active=1 ORDER BY p.price""",
            (service_id,)
        )

    def get_service(self, sid):
        return self.fetchone("""
            SELECT s.*, st.name as type_name, st.label_ar as type_label_ar
            FROM services s
            LEFT JOIN service_types st ON s.type_id = st.id
            WHERE s.id=%s
        """, (sid,))

    def add_service(self, name_ar, name_en, desc_ar, desc_en, category, type_id, min_amount=0):
        return self.execute_returning("""
            INSERT INTO services (name_ar, name_en, description_ar, description_en, category, type_id, min_amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (name_ar, name_en, desc_ar, desc_en, category, type_id, min_amount))

    def update_service_field(self, sid, field, value):
        allowed = {"name_ar", "name_en", "description_ar", "description_en", "category", "min_amount"}
        if field not in allowed:
            return
        self.execute(f"UPDATE services SET {field}=%s WHERE id=%s", (value, sid))

    def toggle_service(self, sid, active):
        self.execute("UPDATE services SET is_active=%s WHERE id=%s", (active, sid))

    def delete_service(self, sid):
        self.execute("UPDATE services SET is_active=0 WHERE id=%s", (sid,))

    # ══════════════════════════════
    #   Plans
    # ══════════════════════════════

    def get_plans(self, sid):
        return self.fetch("SELECT * FROM plans WHERE service_id=%s AND is_active=1 ORDER BY price", (sid,))

    def get_plan(self, pid):
        return self.fetchone("""
            SELECT p.*, s.name_ar as service_name_ar, s.name_en as service_name_en,
                   s.id as service_id, s.type_id, s.min_amount,
                   st.name as type_name
            FROM plans p
            JOIN services s ON p.service_id = s.id
            JOIN service_types st ON s.type_id = st.id
            WHERE p.id=%s
        """, (pid,))

    def add_plan_full(self, svc_id, name_ar, name_en, days, price, features=None, options=None, variant_id=None):
        self.execute("""
            INSERT INTO plans (service_id, variant_id, name_ar, name_en, duration_days, price, features, extra_options)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (svc_id, variant_id, name_ar, name_en, days, price,
              json.dumps(features or []), json.dumps(options or [])))

    def update_plan_options(self, pid, options):
        self.execute("UPDATE plans SET extra_options=%s WHERE id=%s", (json.dumps(options), pid))

    def update_plan_field(self, pid, field, value):
        allowed = {"name_ar", "name_en", "duration_days", "price"}
        if field not in allowed:
            return
        self.execute(f"UPDATE plans SET {field}=%s WHERE id=%s", (value, pid))

    def get_plan_options(self, pid):
        r = self.fetchone("SELECT extra_options FROM plans WHERE id=%s", (pid,))
        if r:
            return json.loads(r["extra_options"] or "[]")
        return []

    def delete_plan(self, pid):
        self.execute("UPDATE plans SET is_active=0 WHERE id=%s", (pid,))

    # ══════════════════════════════
    #   Exchange Rates
    # ══════════════════════════════

    def get_exchange_rate(self, service_id):
        return self.fetchone(
            "SELECT * FROM exchange_rates WHERE service_id=%s ORDER BY updated_at DESC LIMIT 1",
            (service_id,)
        )

    def set_exchange_rate(self, service_id, rate, unit="USDT"):
        existing = self.get_exchange_rate(service_id)
        if existing:
            self.execute(
                "UPDATE exchange_rates SET rate=%s, unit=%s, updated_at=NOW() WHERE service_id=%s",
                (rate, unit, service_id)
            )
        else:
            self.execute(
                "INSERT INTO exchange_rates (service_id, rate, unit) VALUES (%s, %s, %s)",
                (service_id, rate, unit)
            )

    # ══════════════════════════════
    #   Orders
    # ══════════════════════════════

    def create_order(self, uid, plan_id, service_id, amount, user_options=None, user_inputs=None):
        return self.execute_returning("""
            INSERT INTO orders (user_id, plan_id, service_id, amount, user_options, user_inputs)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (uid, plan_id, service_id, amount,
              json.dumps(user_options or {}),
              json.dumps(user_inputs or {})))

    def get_order(self, order_id):
        return self.fetchone("SELECT * FROM orders WHERE id=%s", (order_id,))

    def update_order_status(self, order_id, status):
        self.execute("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))

    def complete_order(self, order_id):
        self.execute(
            "UPDATE orders SET status='paid', paid_at=NOW() WHERE id=%s",
            (order_id,)
        )
        return self.get_order(order_id)

    def get_pending_orders(self):
        return self.fetch("""
            SELECT o.*, u.full_name, u.username,
                   p.name_ar as plan_name_ar, p.name_en as plan_name_en,
                   s.name_ar as svc_ar, s.name_en as svc_en
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN plans p ON o.plan_id = p.id
            JOIN services s ON o.service_id = s.id
            WHERE o.status = 'awaiting_approval'
            ORDER BY o.created_at DESC
        """)


    def get_subscription_orders(self, status=None, page=0, per_page=5, search=None):
        """طلبات الاشتراكات مع pagination وبحث"""
        offset = page * per_page
        conditions = ["o.order_type != 'recharge'"]
        params = []
        if status:
            conditions.append("o.status = %s")
            params.append(status)
        if search:
            conditions.append("(u.full_name ILIKE %s OR u.username ILIKE %s OR CAST(o.id AS TEXT) = %s)")
            params += [f"%{search}%", f"%{search}%", search]
        where = " AND ".join(conditions)
        rows = self.fetch(f"""
            SELECT o.*, u.full_name, u.username,
                   p.name_ar as plan_name_ar,
                   s.name_ar as svc_ar
            FROM orders o
            JOIN users u ON o.user_id = u.id
            LEFT JOIN plans p ON o.plan_id = p.id
            JOIN services s ON o.service_id = s.id
            WHERE {where}
            ORDER BY o.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])
        total = self.fetchone(f"""
            SELECT COUNT(*) as c FROM orders o
            JOIN users u ON o.user_id = u.id
            LEFT JOIN plans p ON o.plan_id = p.id
            JOIN services s ON o.service_id = s.id
            WHERE {where}
        """, params)["c"]
        return rows, total

    def get_recharge_orders(self, status=None, page=0, per_page=5, search=None):
        """طلبات التعبئة مع pagination وبحث"""
        offset = page * per_page
        conditions = ["o.order_type = 'recharge'"]
        params = []
        if status:
            conditions.append("o.status = %s")
            params.append(status)
        if search:
            conditions.append("(u.full_name ILIKE %s OR u.username ILIKE %s OR CAST(o.id AS TEXT) = %s OR o.phone_number ILIKE %s)")
            params += [f"%{search}%", f"%{search}%", search, f"%{search}%"]
        where = " AND ".join(conditions)
        rows = self.fetch(f"""
            SELECT o.*, u.full_name, u.username,
                   s.name_ar as svc_ar
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN services s ON o.service_id = s.id
            WHERE {where}
            ORDER BY o.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])
        total = self.fetchone(f"""
            SELECT COUNT(*) as c FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN services s ON o.service_id = s.id
            WHERE {where}
        """, params)["c"]
        return rows, total

    def get_order_by_id(self, order_id):
        return self.fetchone("""
            SELECT o.*, u.full_name, u.username,
                   p.name_ar as plan_name_ar,
                   s.name_ar as svc_ar
            FROM orders o
            JOIN users u ON o.user_id = u.id
            LEFT JOIN plans p ON o.plan_id = p.id
            JOIN services s ON o.service_id = s.id
            WHERE o.id = %s
        """, (order_id,))

    def approve_subscription_order(self, order_id):
        self.execute("UPDATE orders SET status='paid', paid_at=NOW() WHERE id=%s", (order_id,))

    def reject_order(self, order_id):
        self.execute("UPDATE orders SET status='rejected' WHERE id=%s", (order_id,))

    # ══════════════════════════════
    #   Subscriptions
    # ══════════════════════════════

    def create_subscription(self, uid, plan_id, order_id, service_id, days, credentials="{}"):
        if days and days > 0:
            expires = datetime.now() + timedelta(days=days)
        else:
            expires = datetime.now() + timedelta(days=3650)  # خدمات بدون مدة محددة
        self.execute("""
            INSERT INTO subscriptions (user_id, plan_id, order_id, service_id, expires_at, credentials)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (uid, plan_id, order_id, service_id, expires, credentials))

    def get_active_subscription(self, uid):
        return self.fetchone("""
            SELECT sub.*, p.name_ar as plan_name, p.name_en as plan_name_en,
                   p.duration_days, s.name_ar as service_ar, s.name_en as service_en
            FROM subscriptions sub
            JOIN plans p ON sub.plan_id = p.id
            JOIN services s ON sub.service_id = s.id
            WHERE sub.user_id=%s AND sub.status='active' AND sub.expires_at > NOW()
            ORDER BY sub.expires_at DESC LIMIT 1
        """, (uid,))

    def get_all_subscriptions(self, uid):
        return self.fetch("""
            SELECT sub.*, p.name_ar as plan_name, p.duration_days,
                   s.name_ar as service_ar
            FROM subscriptions sub
            JOIN plans p ON sub.plan_id = p.id
            JOIN services s ON sub.service_id = s.id
            WHERE sub.user_id=%s ORDER BY sub.started_at DESC
        """, (uid,))

    def get_subscriptions_admin(self, status="all", page=0, per_page=5, search=""):
        """Get all subscriptions for admin panel with pagination and search."""
        offset = page * per_page
        conditions = []
        params = []

        if status == "active":
            conditions.append("sub.status='active' AND sub.expires_at > NOW()")
        elif status == "expired":
            conditions.append("(sub.status='cancelled' OR sub.expires_at <= NOW())")

        if search:
            conditions.append(
                "(u.username ILIKE %s OR CAST(u.id AS TEXT) LIKE %s OR CAST(sub.id AS TEXT) LIKE %s)"
            )
            s = f"%{search}%"
            params += [s, s, s]

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        rows = self.fetch(f"""
            SELECT sub.id, sub.status, sub.started_at, sub.expires_at,
                   sub.credentials,
                   u.id as user_id, u.username, u.full_name,
                   p.name_ar as plan_name, p.duration_days,
                   s.name_ar as service_name
            FROM subscriptions sub
            JOIN users u ON sub.user_id = u.id
            JOIN plans p ON sub.plan_id = p.id
            JOIN services s ON sub.service_id = s.id
            {where}
            ORDER BY sub.started_at DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])

        total_row = self.fetchone(f"""
            SELECT COUNT(*) as c
            FROM subscriptions sub
            JOIN users u ON sub.user_id = u.id
            JOIN plans p ON sub.plan_id = p.id
            JOIN services s ON sub.service_id = s.id
            {where}
        """, params)
        total = total_row["c"] if total_row else 0
        return rows or [], total

    def get_subscription_by_id(self, sub_id):
        return self.fetchone("""
            SELECT sub.*, u.username, u.full_name, u.id as user_id,
                   p.name_ar as plan_name, p.duration_days,
                   s.name_ar as service_name
            FROM subscriptions sub
            JOIN users u ON sub.user_id = u.id
            JOIN plans p ON sub.plan_id = p.id
            JOIN services s ON sub.service_id = s.id
            WHERE sub.id = %s
        """, (sub_id,))

    def cancel_subscription(self, sub_id):
        self.execute(
            "UPDATE subscriptions SET status='cancelled' WHERE id=%s",
            (sub_id,)
        )

    def extend_subscription(self, sub_id, days):
        self.execute("""
            UPDATE subscriptions
            SET expires_at = GREATEST(expires_at, NOW()) + INTERVAL '%s days',
                status = 'active'
            WHERE id = %s
        """, (days, sub_id))

    def get_expiring_soon(self, days=3):
        threshold = datetime.now() + timedelta(days=days)
        return self.fetch("""
            SELECT sub.*, u.id as user_id, p.name_ar as plan_name,
                   p.duration_days, s.name_ar as service_ar
            FROM subscriptions sub
            JOIN users u ON sub.user_id = u.id
            JOIN plans p ON sub.plan_id = p.id
            JOIN services s ON sub.service_id = s.id
            WHERE sub.status='active'
              AND sub.expires_at <= %s
              AND sub.expires_at > NOW()
        """, (threshold,))

    def update_subscription_credentials(self, sub_id, credentials):
        self.execute(
            "UPDATE subscriptions SET credentials=%s WHERE id=%s",
            (json.dumps(credentials), sub_id)
        )

    # ══════════════════════════════
    #   Tickets
    # ══════════════════════════════

    def create_ticket(self, uid, message):
        return self.execute_returning(
            "INSERT INTO tickets (user_id, message) VALUES (%s, %s) RETURNING id",
            (uid, message)
        )

    def get_open_tickets(self):
        return self.fetch("""
            SELECT t.*, u.full_name, u.username
            FROM tickets t JOIN users u ON t.user_id = u.id
            WHERE t.status='open' ORDER BY t.created_at DESC
        """)

    def reply_ticket(self, ticket_id, reply):
        self.execute(
            "UPDATE tickets SET reply=%s, status='closed' WHERE id=%s",
            (reply, ticket_id)
        )
        return self.fetchone("SELECT * FROM tickets WHERE id=%s", (ticket_id,))

    # ══════════════════════════════
    #   Stats
    # ══════════════════════════════

    def get_stats(self):
        return {
            "total_users":    self.fetchone("SELECT COUNT(*) as c FROM users")["c"],
            "active_subs":    self.fetchone("SELECT COUNT(*) as c FROM subscriptions WHERE status='active' AND expires_at > NOW()")["c"],
            "total_revenue":  round(self.fetchone("SELECT COALESCE(SUM(amount),0) as c FROM orders WHERE status='paid'")["c"], 2),
            "pending_orders": self.fetchone("SELECT COUNT(*) as c FROM orders WHERE status='awaiting_approval'")["c"],
            "open_tickets":   self.fetchone("SELECT COUNT(*) as c FROM tickets WHERE status='open'")["c"],
        }

    def get_revenue_by_period(self, period="month"):
        """Revenue + order count grouped by day for the given period."""
        if period == "day":
            interval = "1 day"
            trunc = "hour"
        elif period == "week":
            interval = "7 days"
            trunc = "day"
        else:  # month
            interval = "30 days"
            trunc = "day"

        return self.fetch(f"""
            SELECT
                DATE_TRUNC('{trunc}', paid_at) as period,
                COALESCE(SUM(amount), 0) as revenue,
                COUNT(*) as orders
            FROM orders
            WHERE status='paid'
              AND paid_at >= NOW() - INTERVAL '{interval}'
            GROUP BY 1
            ORDER BY 1
        """)

    def get_revenue_by_service(self, period="month"):
        """Revenue per service for the given period."""
        if period == "day":
            interval = "1 day"
        elif period == "week":
            interval = "7 days"
        else:
            interval = "30 days"

        return self.fetch(f"""
            SELECT
                s.name_ar as service_name,
                COALESCE(SUM(o.amount), 0) as revenue,
                COUNT(*) as orders
            FROM orders o
            JOIN services s ON o.service_id = s.id
            WHERE o.status='paid'
              AND o.paid_at >= NOW() - INTERVAL '{interval}'
            GROUP BY s.id, s.name_ar
            ORDER BY revenue DESC
        """)

    def get_summary_stats(self, period="month"):
        """Quick summary numbers for a period."""
        if period == "day":
            interval = "1 day"
        elif period == "week":
            interval = "7 days"
        else:
            interval = "30 days"

        revenue = self.fetchone(f"""
            SELECT COALESCE(SUM(amount),0) as c FROM orders
            WHERE status='paid' AND paid_at >= NOW() - INTERVAL '{interval}'
        """)
        orders = self.fetchone(f"""
            SELECT COUNT(*) as c FROM orders
            WHERE status='paid' AND paid_at >= NOW() - INTERVAL '{interval}'
        """)
        new_users = self.fetchone(f"""
            SELECT COUNT(*) as c FROM users
            WHERE joined_at >= NOW() - INTERVAL '{interval}'
        """)
        new_subs = self.fetchone(f"""
            SELECT COUNT(*) as c FROM subscriptions
            WHERE started_at >= NOW() - INTERVAL '{interval}'
        """)
        return {
            "revenue":   round(revenue["c"], 2) if revenue else 0,
            "orders":    orders["c"] if orders else 0,
            "new_users": new_users["c"] if new_users else 0,
            "new_subs":  new_subs["c"] if new_subs else 0,
        }
