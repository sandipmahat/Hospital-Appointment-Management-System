import pymysql
import pymysql.err
import config

try:
    from dbutils.pooled_db import PooledDB
except ImportError:  # pragma: no cover - fallback for older DBUtils releases
    try:
        from DBUtils.PooledDB import PooledDB
    except ImportError:
        PooledDB = None

_pool = None


def _build_pool():
    """Create the connection pool lazily so importing this module (or running
    with the database offline) never fails at import time.

    mincached=0 means no connections are opened until first use; maxconnections
    caps how many concurrent connections the app can hold open at once, which
    keeps a single instance from exhausting MySQL's connection limit under
    load.
    """
    return PooledDB(
        creator=pymysql,
        mincached=0,
        maxcached=5,
        maxconnections=20,
        blocking=True,
        ping=1,  # ping=1 -> validate the connection whenever it's requested
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_connection():
    """Return a pooled pymysql connection.

    Falls back to a single direct connection if DBUtils isn't installed, so
    the app still runs (just without pooling) in a minimal environment.
    """
    global _pool

    if PooledDB is None:
        return pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor,
        )

    if _pool is None:
        _pool = _build_pool()

    return _pool.connection()


def record_login_event(user_id, username, event_type, ip_address=None,
                       user_agent=None, notes=None):
    """Persist one authentication event without affecting the user's request."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO login_events
                    (user_id, username, event_type, ip_address, user_agent, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, username, event_type, ip_address, user_agent, notes),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    except pymysql.MySQLError:
        return False
    return True


def _bootstrap_connection():
    """A raw, unpooled connection used only during startup table creation,
    where the target database may not exist yet."""
    try:
        return pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor,
        )
    except pymysql.err.OperationalError as e:
        err_no = e.args[0] if e.args else None
        if err_no != 1049:  # 1049 = Unknown database
            raise

        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DATABASE}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor,
        )


def _index_exists(cursor, table_name, index_name):
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = %s AND table_name = %s AND index_name = %s
        LIMIT 1
        """,
        (config.MYSQL_DATABASE, table_name, index_name),
    )
    return cursor.fetchone() is not None


def _add_index(cursor, table_name, index_name, columns):
    if not _index_exists(cursor, table_name, index_name):
        cursor.execute(
            f"CREATE INDEX `{index_name}` ON `{table_name}` ({columns})"
        )


def _column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (config.MYSQL_DATABASE, table_name, column_name),
    )
    return cursor.fetchone() is not None


def create_tables():
    conn = _bootstrap_connection()
    cursor = None
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration safety net for databases created before doctor profile
        # metadata was tracked per-account instead of in a fixed in-code
        # tuple. NULL for every non-doctor row; NULL department/specialty/
        # image on a doctor row just falls back to a generic display at
        # render time (see get_doctor_profiles() in authController.py).
        if not _column_exists(cursor, "users", "department"):
            cursor.execute("ALTER TABLE users ADD COLUMN department VARCHAR(100) NULL")
        if not _column_exists(cursor, "users", "specialty"):
            cursor.execute("ALTER TABLE users ADD COLUMN specialty VARCHAR(100) NULL")
        if not _column_exists(cursor, "users", "image"):
            cursor.execute("ALTER TABLE users ADD COLUMN image VARCHAR(150) NULL")

        # A short doctor bio the admin can fill in from Manage Doctor
        # Accounts - purely descriptive, shown on the doctor's profile page.
        # NULL for patients/admin, and NULL is fine for a doctor too (the
        # profile page just falls back to a generic line).
        if not _column_exists(cursor, "users", "bio"):
            cursor.execute("ALTER TABLE users ADD COLUMN bio VARCHAR(500) NULL")

        # Base32 TOTP secret for the admin account's two-factor login. NULL
        # until the admin actually finishes the "set up 2FA" step, which is
        # how login() decides whether to ask for a 6-digit code at all - an
        # admin who has never opted in keeps logging in with just a password.
        if not _column_exists(cursor, "users", "totp_secret"):
            cursor.execute("ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64) NULL")

        # Seed the single administrator account. There is exactly one admin
        # in this system and it is never created through the login form -
        # only here, at startup. Checked by ADMIN_EMAIL specifically (not
        # "does any admin row exist") so that an old admin account left over
        # from an earlier .env configuration can't silently block the
        # currently configured admin email from ever being created.
        cursor.execute("SELECT id FROM users WHERE email = %s", (config.ADMIN_EMAIL,))
        if not cursor.fetchone():
            from werkzeug.security import generate_password_hash

            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ("Administrator", config.ADMIN_EMAIL, generate_password_hash(config.ADMIN_PASSWORD), "admin"),
            )

        # Seed the six doctor login accounts so the hospital has real
        # doctors to log in as from day one, matching DOCTOR_PROFILES in
        # authController.py by name exactly. Imported locally (not at module
        # level) to avoid a circular import, since authController imports
        # from this module.
        from apps.controllers.authController import DOCTOR_PROFILES
        from werkzeug.security import generate_password_hash

        for profile in DOCTOR_PROFILES:
            cursor.execute("SELECT id FROM users WHERE name = %s AND role = 'doctor'", (profile["name"],))
            existing_doctor = cursor.fetchone()
            if existing_doctor:
                # Backfill department/specialty/image for doctor rows created
                # before those columns existed, so existing deployments don't
                # lose their homepage card/icon data after this migration.
                cursor.execute(
                    """
                    UPDATE users SET department = %s, specialty = %s, image = %s
                    WHERE id = %s AND (department IS NULL OR specialty IS NULL OR image IS NULL)
                    """,
                    (profile["department"], profile["specialty"], profile["image"], existing_doctor["id"]),
                )
                continue
            slug = profile["name"].replace("Dr. ", "").lower().replace(" ", ".")
            email = f"{slug}@sandyhub.com.np"
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                continue
            cursor.execute(
                "INSERT INTO users (name, email, password, role, department, specialty, image) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    profile["name"], email, generate_password_hash(config.DOCTOR_SEED_PASSWORD), "doctor",
                    profile["department"], profile["specialty"], profile["image"],
                ),
            )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                doctor_name VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                appointment_date DATE NOT NULL,
                appointment_time TIME NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Migration safety net for databases created before `updated_at` was
        # added to the CREATE TABLE statement above. Must run after the
        # CREATE TABLE, not before - `appointments` may not exist yet on a
        # fresh database, and ALTERing a table that doesn't exist raises.
        if not _column_exists(cursor, "appointments", "updated_at"):
            cursor.execute(
                """
                ALTER TABLE appointments
                ADD COLUMN updated_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                """
            )

        # Optional note the admin can leave when cancelling an appointment,
        # shown back to the patient on My Appointments so a cancellation
        # doesn't arrive with no explanation. NULL for every other status.
        if not _column_exists(cursor, "appointments", "cancellation_reason"):
            cursor.execute(
                "ALTER TABLE appointments ADD COLUMN cancellation_reason VARCHAR(255) NULL"
            )

        # One-time tokens for the "forgot your password" flow. A row is
        # created when the link is requested and marked used the moment it's
        # consumed, so the same emailed link can't be replayed to reset the
        # password a second time. expires_at is checked in the controller,
        # not enforced here - MySQL doesn't need to know about that rule.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token VARCHAR(64) NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                used TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Lets a doctor block out a whole day (time_slot NULL) or a single
        # slot on a day (time_slot set) so the booking form and the
        # double-booking guard both treat it the same as an already-booked
        # slot, without needing a fake appointment row to represent "closed".
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctor_unavailability (
                id INT AUTO_INCREMENT PRIMARY KEY,
                doctor_name VARCHAR(100) NOT NULL,
                unavailable_date DATE NOT NULL,
                time_slot VARCHAR(10) NULL,
                reason VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # A durable log of every "email" the app has ever sent. There's no
        # real mail server configured for this coursework build, so
        # send_notification() (authController.py) writes here instead of
        # actually dispatching SMTP - the admin can open Notification Log
        # and see exactly what would have gone out, to whom, and when.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                recipient_email VARCHAR(100) NOT NULL,
                subject VARCHAR(200) NOT NULL,
                body TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_events (
                event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                username VARCHAR(100) NOT NULL,
                event_type ENUM('login_success', 'login_failure', 'logout',
                                'password_reset', 'account_locked') NOT NULL,
                ip_address VARCHAR(45) NULL,
                user_agent VARCHAR(255) NULL,
                device_type VARCHAR(50) NULL,
                location VARCHAR(100) NULL,
                event_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                notes VARCHAR(255) NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        _add_index(cursor, "login_events", "idx_login_events_user_time", "`user_id`, `event_time`")
        _add_index(cursor, "login_events", "idx_login_events_type_time", "`event_type`, `event_time`")

        _add_index(cursor, "password_resets", "idx_password_resets_token", "`token`")
        _add_index(cursor, "doctor_unavailability", "idx_doctor_unavail_lookup", "`doctor_name`, `unavailable_date`")

        _add_index(cursor, "users", "idx_users_role", "`role`")
        _add_index(cursor, "users", "idx_users_created_at", "`created_at`")
        _add_index(cursor, "appointments", "idx_appointments_user_id", "`user_id`")
        _add_index(cursor, "appointments", "idx_appointments_status", "`status`")
        _add_index(cursor, "appointments", "idx_appointments_doctor_name", "`doctor_name`")
        _add_index(
            cursor,
            "appointments",
            "idx_appointments_schedule",
            "`appointment_date`, `appointment_time`",
        )
        _add_index(
            cursor,
            "appointments",
            "idx_appointments_user_status",
            "`user_id`, `status`",
        )

        conn.commit()
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def insert_row(table, allowed_fields, data):
    """
    Insert a row into `table` using only keys present in `allowed_fields`.
    `data` is a mapping (e.g., request.form or dict). Returns the new row id.
    This prevents mass-assignment by ignoring unexpected fields.
    """
    # Filter only permitted columns and preserve order from allowed_fields
    cols = [col for col in allowed_fields if col in data]
    if not cols:
        raise ValueError("No valid fields provided for insert")

    placeholders = ", ".join(["%s"] * len(cols))
    cols_sql = ", ".join(cols)
    vals = [data[col] for col in cols]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})",
                tuple(vals),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
    finally:
        conn.close()


def select_one(table, where_clause, params=None, columns="*"):
    """Return a single row matching `where_clause` (SQL fragment after WHERE).
    Example: select_one('users', 'id = %s', (user_id,), columns='id, name')
    """
    params = params or ()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            sql = f"SELECT {columns} FROM {table} WHERE {where_clause} LIMIT 1"
            cursor.execute(sql, params)
            return cursor.fetchone()
        finally:
            cursor.close()
    finally:
        conn.close()


def select_all(table, where_clause=None, params=None, columns="*", order_by=None,
                limit=None, offset=None):
    """Return rows optionally filtered by `where_clause`, ordered, and paged.

    `limit`/`offset` are opt-in so existing callers are unaffected; pass them
    to page through large result sets (e.g. the admin dashboard) instead of
    loading an entire table into memory.

    Example: select_all('appointments', 'user_id = %s', (user_id,),
                         order_by='appointment_date ASC', limit=20, offset=0)
    """
    params = list(params or ())
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            sql = f"SELECT {columns} FROM {table}"
            if where_clause:
                sql += f" WHERE {where_clause}"
            if order_by:
                sql += f" ORDER BY {order_by}"
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
                if offset is not None:
                    sql += " OFFSET %s"
                    params.append(int(offset))
            cursor.execute(sql, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()
    finally:
        conn.close()


def count_rows(table, where_clause=None, params=None):
    """Return the total row count matching an optional filter, for computing
    pagination totals without pulling every row back."""
    params = params or ()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            sql = f"SELECT COUNT(*) AS total FROM {table}"
            if where_clause:
                sql += f" WHERE {where_clause}"
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return row["total"] if row else 0
        finally:
            cursor.close()
    finally:
        conn.close()
