"""Database scalability visualizer API bridge — MySQL primary-replica."""

import contextlib
import json
import os
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

import pymysql

PRIMARY_HOST = os.environ.get("MYSQL_PRIMARY_HOST", "mysql-primary")
REPLICA_HOST = os.environ.get("MYSQL_REPLICA_HOST", "mysql-replica")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASS = os.environ.get("MYSQL_PASS", "rootpass")
MYSQL_DB = os.environ.get("MYSQL_DB", "university")


def get_conn(host):
    """Return a MySQL connection to the specified host."""
    return pymysql.connect(
        host=host, user=MYSQL_USER, password=MYSQL_PASS,
        database=MYSQL_DB, cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def step_entry(seq, action, target, result, latency_ms, data=None):
    """Build a single step trace entry."""
    entry = {
        "seq": seq, "action": action, "target": target,
        "result": result, "latency_ms": round(latency_ms, 2),
    }
    if data is not None:
        entry["data"] = data
    return entry


# ---- Replication Tab ----

def replication_write(body):
    """Insert a student on the primary and read from replica."""
    name = body.get("name", "Test Student")
    email = body.get("email", "test@university.edu")
    major = body.get("major", "Computer Science")
    steps = []
    total_start = time.perf_counter()
    seq = 1

    # Write to primary
    conn = get_conn(PRIMARY_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO students (name, email, major) VALUES (%s, %s, %s)",
                (name, email, major),
            )
            new_id = cur.lastrowid
        t1 = time.perf_counter()
        steps.append(step_entry(seq, "INSERT", "primary", "OK",
                                (t1 - t0) * 1000, {"student_id": new_id}))
        seq += 1
    finally:
        conn.close()

    # Read from replica
    conn = get_conn(REPLICA_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE student_id = %s", (new_id,))
            row = cur.fetchone()
        t1 = time.perf_counter()
        found = row is not None
        steps.append(step_entry(
            seq, "SELECT", "replica",
            "FOUND" if found else "NOT YET REPLICATED",
            (t1 - t0) * 1000, row,
        ))
        seq += 1

        # Check replication lag
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("SHOW REPLICA STATUS")
            status = cur.fetchone()
        t1 = time.perf_counter()
        lag = status.get("Seconds_Behind_Source", "N/A") if status else "N/A"
        steps.append(step_entry(seq, "SHOW REPLICA STATUS", "replica", "OK",
                                (t1 - t0) * 1000, {"lag_seconds": lag}))
    finally:
        conn.close()

    total_ms = (time.perf_counter() - total_start) * 1000
    return {"pattern": "replication", "steps": steps, "total_ms": round(total_ms, 2)}


def replication_status(_body):
    """Get current replication status."""
    conn = get_conn(REPLICA_HOST)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW REPLICA STATUS")
            status = cur.fetchone()
        if not status:
            return {"error": "Replication not configured"}
        return {
            "io_running": status.get("Replica_IO_Running"),
            "sql_running": status.get("Replica_SQL_Running"),
            "lag_seconds": status.get("Seconds_Behind_Source"),
            "source_host": status.get("Source_Host"),
        }
    finally:
        conn.close()


# ---- Consistency Tab (ACID Transactions) ----

def consistency_transfer(body):
    """Transfer enrollment between courses in a transaction."""
    student_id = int(body.get("student_id", 1))
    from_course = body.get("from_course", "CS101")
    to_course = body.get("to_course", "PHYS101")
    steps = []
    total_start = time.perf_counter()
    seq = 1

    conn = get_conn(PRIMARY_HOST)
    conn.autocommit(False)
    try:
        t0 = time.perf_counter()
        conn.begin()
        t1 = time.perf_counter()
        steps.append(step_entry(seq, "BEGIN", "primary", "OK", (t1 - t0) * 1000))
        seq += 1

        with conn.cursor() as cur:
            # Get course IDs
            cur.execute("SELECT course_id FROM courses WHERE code = %s", (from_course,))
            from_row = cur.fetchone()
            cur.execute("SELECT course_id FROM courses WHERE code = %s", (to_course,))
            to_row = cur.fetchone()

            if not from_row or not to_row:
                conn.rollback()
                return {"error": f"Course not found: {from_course} or {to_course}"}

            from_id = from_row["course_id"]
            to_id = to_row["course_id"]

            # Delete old enrollment
            t0 = time.perf_counter()
            cur.execute("DELETE FROM enrollments WHERE student_id = %s AND course_id = %s",
                        (student_id, from_id))
            affected = cur.rowcount
            t1 = time.perf_counter()
            steps.append(step_entry(seq, f"DELETE enrollment ({from_course})", "primary",
                                    "OK" if affected > 0 else "NO ROWS",
                                    (t1 - t0) * 1000, {"rows_affected": affected}))
            seq += 1

            # Update from-course count
            t0 = time.perf_counter()
            cur.execute("UPDATE courses SET enrolled = enrolled - 1 WHERE course_id = %s AND enrolled > 0",
                        (from_id,))
            t1 = time.perf_counter()
            steps.append(step_entry(seq, f"UPDATE {from_course} enrolled-1", "primary", "OK",
                                    (t1 - t0) * 1000))
            seq += 1

            # Insert new enrollment
            t0 = time.perf_counter()
            try:
                cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s)",
                            (student_id, to_id))
                t1 = time.perf_counter()
                steps.append(step_entry(seq, f"INSERT enrollment ({to_course})", "primary", "OK",
                                        (t1 - t0) * 1000))
            except pymysql.IntegrityError as exc:
                t1 = time.perf_counter()
                conn.rollback()
                steps.append(step_entry(seq, f"INSERT enrollment ({to_course})", "primary",
                                        "CONSTRAINT VIOLATION", (t1 - t0) * 1000,
                                        {"error": str(exc)}))
                steps.append(step_entry(seq + 1, "ROLLBACK", "primary", "OK", 0))
                total_ms = (time.perf_counter() - total_start) * 1000
                return {"pattern": "consistency", "steps": steps,
                        "total_ms": round(total_ms, 2), "outcome": "ROLLED BACK"}
            seq += 1

            # Update to-course count
            t0 = time.perf_counter()
            cur.execute("UPDATE courses SET enrolled = enrolled + 1 WHERE course_id = %s",
                        (to_id,))
            t1 = time.perf_counter()
            steps.append(step_entry(seq, f"UPDATE {to_course} enrolled+1", "primary", "OK",
                                    (t1 - t0) * 1000))
            seq += 1

        # COMMIT
        t0 = time.perf_counter()
        conn.commit()
        t1 = time.perf_counter()
        steps.append(step_entry(seq, "COMMIT", "primary", "OK", (t1 - t0) * 1000))

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "consistency", "steps": steps,
                "total_ms": round(total_ms, 2), "outcome": "COMMITTED"}
    except Exception as exc:
        conn.rollback()
        return {"error": str(exc)}
    finally:
        conn.close()


# ---- Schema Tab (Indexing) ----

def schema_explain(body):
    """Run EXPLAIN on a query with optional index creation."""
    student_id = int(body.get("student_id", 3))
    resource = body.get("resource", "resource-10")
    steps = []
    total_start = time.perf_counter()
    seq = 1

    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            # Run EXPLAIN
            t0 = time.perf_counter()
            cur.execute(
                "EXPLAIN SELECT * FROM access_log WHERE student_id = %s AND resource = %s",
                (student_id, resource),
            )
            plan = cur.fetchone()
            t1 = time.perf_counter()
            steps.append(step_entry(seq, "EXPLAIN", "primary", "OK",
                                    (t1 - t0) * 1000, plan))
            seq += 1

            # Run actual query with timing
            t0 = time.perf_counter()
            cur.execute(
                "SELECT COUNT(*) as cnt FROM access_log WHERE student_id = %s AND resource = %s",
                (student_id, resource),
            )
            result = cur.fetchone()
            t1 = time.perf_counter()
            steps.append(step_entry(seq, "SELECT COUNT(*)", "primary", "OK",
                                    (t1 - t0) * 1000, result))

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "schema", "steps": steps, "total_ms": round(total_ms, 2)}
    finally:
        conn.close()


def schema_add_index(_body):
    """Add composite index on access_log."""
    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            try:
                cur.execute(
                    "CREATE INDEX idx_student_resource ON access_log (student_id, resource)"
                )
                result = "CREATED"
            except pymysql.err.OperationalError:
                result = "ALREADY EXISTS"
            t1 = time.perf_counter()
        return {"action": "CREATE INDEX", "result": result,
                "latency_ms": round((t1 - t0) * 1000, 2)}
    finally:
        conn.close()


def schema_drop_index(_body):
    """Drop the composite index."""
    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            try:
                cur.execute("DROP INDEX idx_student_resource ON access_log")
                result = "DROPPED"
            except pymysql.err.OperationalError:
                result = "NOT FOUND"
            t1 = time.perf_counter()
        return {"action": "DROP INDEX", "result": result,
                "latency_ms": round((t1 - t0) * 1000, 2)}
    finally:
        conn.close()


# ---- Database State ----

def db_state(_body):
    """Gather current database state for sidebar."""
    state = {"primary": {}, "replica": {}}

    # Primary stats
    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM students")
            state["primary"]["students"] = cur.fetchone()["cnt"]
            cur.execute("SELECT code, enrolled FROM courses ORDER BY code")
            state["primary"]["courses"] = cur.fetchall()
            cur.execute("SELECT COUNT(*) as cnt FROM access_log")
            state["primary"]["access_log_rows"] = cur.fetchone()["cnt"]
            cur.execute("SHOW INDEX FROM access_log WHERE Key_name != 'PRIMARY'")
            state["primary"]["indexes"] = [r["Key_name"] for r in cur.fetchall()]
    finally:
        conn.close()

    # Replica lag
    conn = get_conn(REPLICA_HOST)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW REPLICA STATUS")
            rs = cur.fetchone()
            if rs:
                state["replica"]["io_running"] = rs.get("Replica_IO_Running")
                state["replica"]["sql_running"] = rs.get("Replica_SQL_Running")
                state["replica"]["lag"] = rs.get("Seconds_Behind_Source")
            cur.execute("SELECT COUNT(*) as cnt FROM students")
            state["replica"]["students"] = cur.fetchone()["cnt"]
    finally:
        conn.close()

    return state


def db_reset(_body):
    """Reset database to initial state."""
    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM enrollments")
            cur.execute("DELETE FROM students WHERE student_id > 10")
            cur.execute("DELETE FROM courses WHERE code NOT IN ('CS101','CS201','MATH101','PHYS101')")
            cur.execute("""UPDATE courses SET enrolled = CASE code
                WHEN 'CS101' THEN 4 WHEN 'CS201' THEN 2
                WHEN 'MATH101' THEN 2 WHEN 'PHYS101' THEN 2 END""")
            # Re-insert original enrollments
            cur.execute("""INSERT INTO enrollments (student_id, course_id) VALUES
                (1,1),(3,1),(5,1),(8,1),(1,2),(3,2),(2,3),(6,3),(4,4),(9,4)""")
            with contextlib.suppress(pymysql.err.OperationalError):
                cur.execute("DROP INDEX idx_student_resource ON access_log")
        return {"result": "OK", "message": "Database reset to initial state"}
    finally:
        conn.close()


ALLOWED_SQL = frozenset({
    "SELECT", "INSERT", "UPDATE", "DELETE",
    "EXPLAIN", "SHOW", "DESCRIBE", "DESC",
    "ANALYZE", "START", "COMMIT", "ROLLBACK",
})


def sql_exec(body):
    """Execute arbitrary SQL against primary or replica."""
    query = body.get("query", "").strip()
    target = body.get("target", "primary")
    if not query:
        return {"error": "Empty query"}

    # Reject multi-statement queries
    if ";" in query.rstrip(";"):
        return {"error": "Multi-statement queries are not allowed"}

    # Allowlist: only permit known safe SQL commands
    first_word = query.split()[0].upper() if query.split() else ""
    if first_word not in ALLOWED_SQL:
        return {"error": f"Command not allowed: {first_word}. "
                f"Permitted: {', '.join(sorted(ALLOWED_SQL))}"}

    host = REPLICA_HOST if target == "replica" else PRIMARY_HOST
    conn = get_conn(host)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(query)
            if cur.description:
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
                t1 = time.perf_counter()
                return {
                    "columns": columns, "rows": rows,
                    "row_count": len(rows),
                    "latency_ms": round((t1 - t0) * 1000, 2),
                    "target": target, "query": query,
                }
            t1 = time.perf_counter()
            return {
                "affected_rows": cur.rowcount,
                "latency_ms": round((t1 - t0) * 1000, 2),
                "target": target, "query": query,
            }
    except pymysql.MySQLError as exc:
        return {"error": str(exc), "target": target, "query": query}
    finally:
        conn.close()


ROUTES = {
    ("GET", "/api/db/state"): db_state,
    ("POST", "/api/db/reset"): db_reset,
    ("POST", "/api/replication/write"): replication_write,
    ("GET", "/api/replication/status"): replication_status,
    ("POST", "/api/consistency/transfer"): consistency_transfer,
    ("POST", "/api/schema/explain"): schema_explain,
    ("POST", "/api/schema/add-index"): schema_add_index,
    ("POST", "/api/schema/drop-index"): schema_drop_index,
    ("POST", "/api/sql/exec"): sql_exec,
}

MIME_TYPES = {
    ".html": "text/html", ".css": "text/css",
    ".js": "application/javascript", ".svg": "image/svg+xml",
}


class Handler(SimpleHTTPRequestHandler):
    """HTTP request handler for the database visualizer."""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        handler = ROUTES.get(("GET", path))
        if handler:
            self._send_json(handler(None))
            return
        if path == "/":
            path = "/index.html"
        self._serve_static(path)

    def do_POST(self):  # noqa: N802
        path = self.path.split("?")[0]
        handler = ROUTES.get(("POST", path))
        if not handler:
            self._send_json({"error": "Not found"}, 404)
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            raw = self.rfile.read(content_length)
            try:
                body = json.loads(raw.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json({"error": "Invalid JSON body"}, 400)
                return
        try:
            result = handler(body)
            self._send_json(result)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, 500)

    def _send_json(self, data, status=200):
        payload = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, path):
        filename = path.lstrip("/")
        resolved = os.path.realpath(filename)
        if not resolved.startswith(os.path.realpath(os.getcwd())):
            self._send_json({"error": "Forbidden"}, 403)
            return
        ext = os.path.splitext(filename)[1]
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        try:
            with open(resolved, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_json({"error": "Not found"}, 404)

    def log_message(self, format, *args):  # noqa: A002
        pass


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print("Database scalability visualizer listening on :8080")
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)  # noqa: S104
    server.serve_forever()
