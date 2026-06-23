import pymysql
import pymysql.err
import config


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


def get_connection():
    """Return a pymysql connection. If the configured database does not exist,
    create it and retry the connection.
    """
    try:
        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor,
        )

        print("Database connected successfully!")
        return conn

    except pymysql.err.OperationalError as e:
        # Error 1049: Unknown database
        try:
            err_no = e.args[0]
        except Exception:
            err_no = None

        if err_no == 1049:
            print(f"Database '{config.MYSQL_DATABASE}' not found. Creating...")
            # Connect without specifying a database to create it
            conn = pymysql.connect(
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                cursorclass=pymysql.cursors.DictCursor,
            )
            cursor = conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DATABASE}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            conn.commit()
            cursor.close()
            conn.close()
            # Retry connection to the newly created database
            conn = pymysql.connect(
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                database=config.MYSQL_DATABASE,
                cursorclass=pymysql.cursors.DictCursor,
            )
            print("Database created and connected successfully!")
            return conn

        print("Database connection failed:", e)
        raise

    except Exception as e:
        print("Database connection failed:", e)
        raise


def create_tables():
    conn = get_connection()
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

        if not _column_exists(cursor, "appointments", "updated_at"):
            cursor.execute(
                """
                ALTER TABLE appointments
                ADD COLUMN updated_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                """
            )

        cursor.execute("SELECT id FROM users WHERE email = %s", ("admin@admin.com",))
        if not cursor.fetchone():
            from werkzeug.security import generate_password_hash

            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ("Admin", "admin@admin.com", generate_password_hash("admin123"), "admin"),
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

        _add_index(cursor, "users", "idx_users_role", "`role`")
        _add_index(cursor, "users", "idx_users_created_at", "`created_at`")
        _add_index(cursor, "appointments", "idx_appointments_user_id", "`user_id`")
        _add_index(cursor, "appointments", "idx_appointments_status", "`status`")
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
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})",
        tuple(vals),
    )
    conn.commit()
    row_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return row_id


def select_one(table, where_clause, params=None, columns="*"):
    """Return a single row matching `where_clause` (SQL fragment after WHERE).
    Example: select_one('users', 'id = %s', (user_id,), columns='id, name')
    """
    params = params or ()
    conn = get_connection()
    cursor = conn.cursor()
    sql = f"SELECT {columns} FROM {table} WHERE {where_clause} LIMIT 1"
    cursor.execute(sql, params)
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def select_all(table, where_clause=None, params=None, columns="*", order_by=None):
    """Return all rows optionally filtered by `where_clause`.
    Example: select_all('appointments', 'user_id = %s', (user_id,), order_by='appointment_date ASC')
    """
    params = params or ()
    conn = get_connection()
    cursor = conn.cursor()
    sql = f"SELECT {columns} FROM {table}"
    if where_clause:
        sql += f" WHERE {where_clause}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
