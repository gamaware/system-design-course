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


def step_entry(seq, action, target, result, latency_ms, data=None, sql=None):
    """Build a single step trace entry."""
    entry = {
        "seq": seq, "action": action, "target": target,
        "result": result, "latency_ms": round(latency_ms, 2),
    }
    if data is not None:
        entry["data"] = data
    if sql is not None:
        entry["sql"] = sql
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

    insert_sql = f"INSERT INTO students (name, email, major) VALUES ('{name}', '{email}', '{major}')"
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
                                (t1 - t0) * 1000, {"student_id": new_id},
                                sql=insert_sql))
        seq += 1
    finally:
        conn.close()

    select_sql = f"SELECT * FROM students WHERE student_id = {new_id}"
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
            (t1 - t0) * 1000, row, sql=select_sql,
        ))
        seq += 1

        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("SHOW REPLICA STATUS")
            status = cur.fetchone()
        t1 = time.perf_counter()
        lag = status.get("Seconds_Behind_Source", "N/A") if status else "N/A"
        steps.append(step_entry(seq, "SHOW REPLICA STATUS", "replica", "OK",
                                (t1 - t0) * 1000, {"lag_seconds": lag},
                                sql="SHOW REPLICA STATUS"))
    finally:
        conn.close()

    total_ms = (time.perf_counter() - total_start) * 1000
    if found:
        interp = (f"The row appeared on the replica within {round(total_ms, 1)}ms. "
                  f"Replication lag is {lag} seconds. In a read-heavy system, "
                  "distributing SELECTs to replicas reduces primary load -- this is "
                  "horizontal read scaling. The trade-off: replicas may serve "
                  "slightly stale data during lag spikes.")
    else:
        interp = ("The row was NOT found on the replica -- replication has not "
                  "caught up yet. This is replication lag in action. Any application "
                  "reading from replicas must tolerate eventual consistency: the data "
                  "will arrive, but not instantly.")
    return {"pattern": "replication", "steps": steps, "total_ms": round(total_ms, 2),
            "interpretation": interp}


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
            "sql": "SHOW REPLICA STATUS",
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
        steps.append(step_entry(seq, "BEGIN", "primary", "OK", (t1 - t0) * 1000,
                                sql="BEGIN"))
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
            delete_sql = (f"DELETE FROM enrollments WHERE student_id = {student_id} "
                          f"AND course_id = {from_id}")
            t0 = time.perf_counter()
            cur.execute("DELETE FROM enrollments WHERE student_id = %s AND course_id = %s",
                        (student_id, from_id))
            affected = cur.rowcount
            t1 = time.perf_counter()
            steps.append(step_entry(seq, f"DELETE enrollment ({from_course})", "primary",
                                    "OK" if affected > 0 else "NO ROWS",
                                    (t1 - t0) * 1000, {"rows_affected": affected},
                                    sql=delete_sql))
            seq += 1

            # Update from-course count
            update_from_sql = (f"UPDATE courses SET enrolled = enrolled - 1 "
                               f"WHERE course_id = {from_id} AND enrolled > 0")
            t0 = time.perf_counter()
            cur.execute("UPDATE courses SET enrolled = enrolled - 1 WHERE course_id = %s AND enrolled > 0",
                        (from_id,))
            t1 = time.perf_counter()
            steps.append(step_entry(seq, f"UPDATE {from_course} enrolled-1", "primary", "OK",
                                    (t1 - t0) * 1000,
                                    sql=update_from_sql))
            seq += 1

            # Insert new enrollment
            insert_sql = (f"INSERT INTO enrollments (student_id, course_id) "
                          f"VALUES ({student_id}, {to_id})")
            t0 = time.perf_counter()
            try:
                cur.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s)",
                            (student_id, to_id))
                t1 = time.perf_counter()
                steps.append(step_entry(seq, f"INSERT enrollment ({to_course})", "primary", "OK",
                                        (t1 - t0) * 1000, sql=insert_sql))
            except pymysql.IntegrityError as exc:
                t1 = time.perf_counter()
                conn.rollback()
                steps.append(step_entry(seq, f"INSERT enrollment ({to_course})", "primary",
                                        "CONSTRAINT VIOLATION", (t1 - t0) * 1000,
                                        {"error": str(exc)}, sql=insert_sql))
                steps.append(step_entry(seq + 1, "ROLLBACK", "primary", "OK", 0,
                                        sql="ROLLBACK"))
                total_ms = (time.perf_counter() - total_start) * 1000
                return {"pattern": "consistency", "steps": steps,
                        "total_ms": round(total_ms, 2), "outcome": "ROLLED BACK",
                        "interpretation": (
                            "The transaction was ROLLED BACK due to a constraint "
                            "violation. This demonstrates atomicity: none of the "
                            "changes (DELETE, UPDATE, INSERT) were applied. The "
                            "database remains in a consistent state as if the "
                            "transfer was never attempted.")}
            seq += 1

            # Update to-course count
            update_to_sql = (f"UPDATE courses SET enrolled = enrolled + 1 "
                             f"WHERE course_id = {to_id}")
            t0 = time.perf_counter()
            cur.execute("UPDATE courses SET enrolled = enrolled + 1 WHERE course_id = %s",
                        (to_id,))
            t1 = time.perf_counter()
            steps.append(step_entry(seq, f"UPDATE {to_course} enrolled+1", "primary", "OK",
                                    (t1 - t0) * 1000,
                                    sql=update_to_sql))
            seq += 1

        # COMMIT
        t0 = time.perf_counter()
        conn.commit()
        t1 = time.perf_counter()
        steps.append(step_entry(seq, "COMMIT", "primary", "OK", (t1 - t0) * 1000,
                                sql="COMMIT"))

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "consistency", "steps": steps,
                "total_ms": round(total_ms, 2), "outcome": "COMMITTED",
                "interpretation": (
                    f"The transaction COMMITTED successfully in "
                    f"{round(total_ms, 1)}ms. All four operations (DELETE, "
                    f"UPDATE, INSERT, UPDATE) were applied atomically -- either "
                    f"all succeed or none do. This guarantees the enrollment "
                    f"counts stay consistent even if the server crashes "
                    f"mid-transaction.")}
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

    explain_sql = (f"EXPLAIN SELECT * FROM access_log WHERE student_id = {student_id} "
                   f"AND resource = '{resource}'")
    count_sql = (f"SELECT COUNT(*) AS cnt FROM access_log WHERE student_id = {student_id} "
                 f"AND resource = '{resource}'")

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
                                    (t1 - t0) * 1000, plan, sql=explain_sql))
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
                                    (t1 - t0) * 1000, result, sql=count_sql))

        rows_scanned = plan.get("rows", "?") if plan else "?"
        scan_type = plan.get("type", "unknown") if plan else "unknown"
        key_used = plan.get("key") if plan else None
        if key_used:
            interp = (f"The query uses index '{key_used}' ({scan_type}), scanning "
                      f"~{rows_scanned} rows. Index lookups are fast because the "
                      f"engine jumps directly to matching entries instead of reading "
                      f"every row in the table.")
        else:
            interp = (f"The query performs a {scan_type} scanning ~{rows_scanned} rows "
                      f"with no index. Every row in the table must be examined, which "
                      f"gets slower as the table grows. Adding a composite index on "
                      f"(student_id, resource) would reduce this to a few rows.")

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "schema", "steps": steps, "total_ms": round(total_ms, 2),
                "interpretation": interp}
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
                "latency_ms": round((t1 - t0) * 1000, 2),
                "sql": "CREATE INDEX idx_student_resource ON access_log (student_id, resource)"}
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
                "latency_ms": round((t1 - t0) * 1000, 2),
                "sql": "DROP INDEX idx_student_resource ON access_log"}
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

    # Strip mysql CLI formatting suffix (\G) -- not valid SQL
    query = query.rstrip(";").rstrip()
    if query.endswith("\\G"):
        query = query[:-2].rstrip()

    # Reject multi-statement queries
    if ";" in query:
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


# ---- CAP Theorem Tab ----

def cap_stop_replication(_body):
    """Stop replica IO/SQL threads to simulate network partition."""
    conn = get_conn(REPLICA_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("STOP REPLICA")
        t1 = time.perf_counter()
        return {"action": "STOP REPLICA", "result": "STOPPED",
                "latency_ms": round((t1 - t0) * 1000, 2),
                "sql": "STOP REPLICA",
                "interpretation": (
                    "Replication stopped -- the replica will no longer receive "
                    "updates from the primary. This simulates a network partition: "
                    "writes continue on the primary but the replica serves "
                    "increasingly stale data.")}
    finally:
        conn.close()


def cap_start_replication(_body):
    """Restart replica threads to simulate partition recovery."""
    conn = get_conn(REPLICA_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("START REPLICA")
        t1 = time.perf_counter()
        return {"action": "START REPLICA", "result": "STARTED",
                "latency_ms": round((t1 - t0) * 1000, 2),
                "sql": "START REPLICA",
                "interpretation": (
                    "Replication restarted -- the replica will catch up with all "
                    "writes that occurred on the primary during the partition. "
                    "Once lag reaches zero, both nodes are consistent again.")}
    finally:
        conn.close()


def cap_test_divergence(body):
    """Write to primary, read from both, show divergence."""
    name = body.get("name", "CAP Test")
    email = f"cap{int(time.time())}@university.edu"
    steps = []
    total_start = time.perf_counter()
    seq = 1

    # Write to primary
    insert_sql = (f"INSERT INTO students (name, email, major) "
                  f"VALUES ('{name}', '{email}', 'CAP Test')")
    conn = get_conn(PRIMARY_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO students (name, email, major) VALUES (%s, %s, 'CAP Test')",
                        (name, email))
            new_id = cur.lastrowid
        t1 = time.perf_counter()
        steps.append(step_entry(seq, "INSERT", "primary", "OK",
                                (t1 - t0) * 1000, {"student_id": new_id},
                                sql=insert_sql))
        seq += 1
    finally:
        conn.close()

    # Read from primary (should always have it)
    conn = get_conn(PRIMARY_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE student_id = %s", (new_id,))
            row = cur.fetchone()
        t1 = time.perf_counter()
        select_sql = f"SELECT * FROM students WHERE student_id = {new_id}"
        steps.append(step_entry(seq, "SELECT (primary)", "primary",
                                "FOUND" if row else "NOT FOUND",
                                (t1 - t0) * 1000, row, sql=select_sql))
        seq += 1
    finally:
        conn.close()

    # Read from replica (may not have it if replication stopped)
    conn = get_conn(REPLICA_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE student_id = %s", (new_id,))
            row = cur.fetchone()
        t1 = time.perf_counter()
        found = row is not None
        steps.append(step_entry(seq, "SELECT (replica)", "replica",
                                "FOUND (consistent)" if found else "NOT FOUND (stale)",
                                (t1 - t0) * 1000, row, sql=select_sql))
    finally:
        conn.close()

    total_ms = (time.perf_counter() - total_start) * 1000
    diverged = steps[1]["result"] != steps[2]["result"].split(" ")[0]
    if diverged:
        interp = ("The primary and replica returned different results -- the nodes "
                  "have DIVERGED. During a partition, the primary accepted the write "
                  "(availability) but the replica cannot see it (no consistency). "
                  "This is the CA trade-off in action.")
    else:
        interp = ("Both nodes returned the same result -- the system is CONSISTENT. "
                  "With replication active, writes propagate quickly enough that "
                  "both nodes agree. No partition means no CA trade-off.")
    return {
        "pattern": "cap", "steps": steps, "total_ms": round(total_ms, 2),
        "outcome": "DIVERGED (partition active)" if diverged else "CONSISTENT",
        "interpretation": interp,
    }


# ---- Materialized Views Tab ----

def views_create(_body):
    """Create a materialized view (table from SELECT) for enrollment summary."""
    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute("DROP TABLE IF EXISTS enrollment_summary")
            cur.execute("""
                CREATE TABLE enrollment_summary AS
                SELECT s.student_id, s.name, s.major,
                       c.code AS course_code, c.title AS course_title,
                       e.enrolled_at
                FROM enrollments e
                JOIN students s ON e.student_id = s.student_id
                JOIN courses c ON e.course_id = c.course_id
            """)
            cur.execute("SELECT COUNT(*) AS cnt FROM enrollment_summary")
            cnt = cur.fetchone()["cnt"]
            t1 = time.perf_counter()
        create_sql = ("CREATE TABLE enrollment_summary AS "
                      "SELECT s.student_id, s.name, s.major, "
                      "c.code AS course_code, c.title AS course_title, "
                      "e.enrolled_at "
                      "FROM enrollments e "
                      "JOIN students s ON e.student_id = s.student_id "
                      "JOIN courses c ON e.course_id = c.course_id")
        return {"action": "CREATE VIEW", "result": "CREATED",
                "rows": cnt, "latency_ms": round((t1 - t0) * 1000, 2),
                "sql": create_sql,
                "interpretation": (
                    f"Pre-computed {cnt} rows into a flat table by joining "
                    f"students, courses, and enrollments once. Future reads "
                    f"hit this single table instead of computing the 3-table "
                    f"JOIN every time -- a classic space-for-time trade-off.")}
    finally:
        conn.close()


def views_drop(_body):
    """Drop the materialized view table."""
    conn = get_conn(PRIMARY_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS enrollment_summary")
        t1 = time.perf_counter()
        return {"action": "DROP VIEW", "result": "DROPPED",
                "latency_ms": round((t1 - t0) * 1000, 2)}
    finally:
        conn.close()


def views_query_join(_body):
    """Run the 3-table JOIN query with timing."""
    conn = get_conn(PRIMARY_HOST)
    try:
        steps = []
        seq = 1
        total_start = time.perf_counter()

        with conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute("""
                SELECT s.name, s.major, c.code, c.title, e.enrolled_at
                FROM enrollments e
                JOIN students s ON e.student_id = s.student_id
                JOIN courses c ON e.course_id = c.course_id
                ORDER BY s.name
            """)
            rows = cur.fetchall()
            t1 = time.perf_counter()
            join_sql = ("SELECT s.name, s.major, c.code, c.title, e.enrolled_at "
                        "FROM enrollments e "
                        "JOIN students s ON e.student_id = s.student_id "
                        "JOIN courses c ON e.course_id = c.course_id "
                        "ORDER BY s.name")
            steps.append(step_entry(seq, "SELECT with 3-table JOIN", "primary",
                                    "OK", (t1 - t0) * 1000,
                                    {"row_count": len(rows)}, sql=join_sql))
            seq += 1

            # Get EXPLAIN
            t0 = time.perf_counter()
            cur.execute("""
                EXPLAIN SELECT s.name, s.major, c.code, c.title, e.enrolled_at
                FROM enrollments e
                JOIN students s ON e.student_id = s.student_id
                JOIN courses c ON e.course_id = c.course_id
            """)
            plan = cur.fetchall()
            t1 = time.perf_counter()
            tables_scanned = len(plan)
            explain_join_sql = ("EXPLAIN SELECT s.name, s.major, c.code, c.title, "
                                "e.enrolled_at FROM enrollments e "
                                "JOIN students s ON e.student_id = s.student_id "
                                "JOIN courses c ON e.course_id = c.course_id")
            steps.append(step_entry(seq, "EXPLAIN (tables scanned)", "primary",
                                    f"{tables_scanned} tables", (t1 - t0) * 1000,
                                    sql=explain_join_sql))

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "views-join", "steps": steps,
                "total_ms": round(total_ms, 2), "row_count": len(rows),
                "interpretation": (
                    f"The 3-table JOIN scanned {tables_scanned} tables to produce "
                    f"{len(rows)} rows in {round(total_ms, 1)}ms. Each query "
                    f"recomputes the join at read time. With more data or complex "
                    f"joins, this cost grows -- materialized views trade storage "
                    f"for faster reads.")}
    finally:
        conn.close()


def views_query_view(_body):
    """Query the pre-computed materialized view."""
    conn = get_conn(PRIMARY_HOST)
    try:
        steps = []
        total_start = time.perf_counter()

        with conn.cursor() as cur:
            # Check if view exists
            cur.execute("SHOW TABLES LIKE 'enrollment_summary'")
            if not cur.fetchone():
                return {"error": "View not created yet. Click 'Create View' first."}

            t0 = time.perf_counter()
            cur.execute("SELECT * FROM enrollment_summary ORDER BY name")
            rows = cur.fetchall()
            t1 = time.perf_counter()
            view_sql = "SELECT * FROM enrollment_summary ORDER BY name"
            query_ms = (t1 - t0) * 1000
            steps.append(step_entry(1, "SELECT from materialized view", "primary",
                                    "OK", query_ms,
                                    {"row_count": len(rows)}, sql=view_sql))

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "views-view", "steps": steps,
                "total_ms": round(total_ms, 2), "row_count": len(rows),
                "interpretation": (
                    f"Reading {len(rows)} rows from the pre-computed table took "
                    f"{round(query_ms, 2)}ms -- no joins needed. Compare this "
                    f"with the JOIN query to see the speed difference. The "
                    f"trade-off: this data is a snapshot and may become stale "
                    f"when the source tables change.")}
    finally:
        conn.close()


def views_refresh(_body):
    """Refresh the materialized view (drop + recreate)."""
    result = views_create(_body)
    if "interpretation" in result:
        result["interpretation"] = (
            "The materialized view was dropped and recreated with current data. "
            "Any changes made to students, courses, or enrollments since the last "
            "refresh are now reflected. In production, refreshes are scheduled "
            "periodically -- the interval determines how stale the data can get.")
    return result


# ---- Vertical Scalability Tab ----

def vertical_set_buffer(body):
    """Set InnoDB buffer pool size."""
    size = body.get("size", "64M")
    conn = get_conn(PRIMARY_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(f"SET GLOBAL innodb_buffer_pool_size = {size}")
        t1 = time.perf_counter()
        return {"action": "SET BUFFER POOL", "size": size,
                "latency_ms": round((t1 - t0) * 1000, 2),
                "sql": f"SET GLOBAL innodb_buffer_pool_size = {size}",
                "interpretation": (
                    f"Buffer pool resized to {size}. A larger pool keeps more "
                    f"data pages in memory, reducing disk reads and improving "
                    f"query latency -- this is vertical scaling in action.")}
    except pymysql.MySQLError as exc:
        return {"error": str(exc)}
    finally:
        conn.close()


def vertical_benchmark(body):
    """Run random queries and measure performance."""
    count = int(body.get("count", 200))
    conn = get_conn(PRIMARY_HOST)
    try:
        steps = []
        total_start = time.perf_counter()
        latencies = []

        # Reset buffer pool stats
        with conn.cursor() as cur:
            cur.execute("FLUSH STATUS")

        with conn.cursor() as cur:
            import random
            for i in range(count):
                sid = random.randint(1, 10)
                rid = f"resource-{random.randint(1, 50)}"
                t0 = time.perf_counter()
                cur.execute(
                    "SELECT * FROM access_log WHERE student_id = %s AND resource = %s",
                    (sid, rid))
                cur.fetchall()
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000)

        # Get buffer pool stats
        with conn.cursor() as cur:
            cur.execute("SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_read_requests'")
            read_requests = int(cur.fetchone().get("Value", 0))
            cur.execute("SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_reads'")
            disk_reads = int(cur.fetchone().get("Value", 0))
            cur.execute("SHOW GLOBAL VARIABLES LIKE 'innodb_buffer_pool_size'")
            pool_size = cur.fetchone().get("Value", "0")

        hit_ratio = round((1 - disk_reads / max(read_requests, 1)) * 100, 1)
        avg_latency = round(sum(latencies) / len(latencies), 2)
        p95 = round(sorted(latencies)[int(len(latencies) * 0.95)], 2)
        qps = round(count / ((time.perf_counter() - total_start)), 1)

        bench_sql = ("SELECT * FROM access_log WHERE student_id = ? "
                     f"AND resource = ? (x{count})")
        if hit_ratio >= 99:
            interp = (f"Buffer hit ratio is {hit_ratio}% -- nearly all reads served "
                      f"from memory ({read_requests} memory reads vs {disk_reads} "
                      f"disk reads). The buffer pool is large enough to cache the "
                      f"working set, so adding more memory would yield diminishing "
                      f"returns.")
        elif hit_ratio >= 90:
            interp = (f"Buffer hit ratio is {hit_ratio}% -- most reads come from "
                      f"memory but {disk_reads} still hit disk. Increasing the "
                      f"buffer pool size would push more pages into cache and "
                      f"reduce average latency.")
        else:
            interp = (f"Buffer hit ratio is only {hit_ratio}% -- {disk_reads} out "
                      f"of {read_requests} reads went to disk. The buffer pool is "
                      f"too small to hold the working set. Increasing memory "
                      f"(vertical scaling) would significantly improve throughput.")

        total_ms = (time.perf_counter() - total_start) * 1000
        return {
            "pattern": "vertical", "total_ms": round(total_ms, 2),
            "sql": bench_sql,
            "interpretation": interp,
            "stats": {
                "queries": count,
                "avg_latency_ms": avg_latency,
                "p95_latency_ms": p95,
                "queries_per_sec": qps,
                "buffer_pool_size": pool_size,
                "buffer_hit_ratio": hit_ratio,
                "disk_reads": disk_reads,
                "memory_reads": read_requests,
            },
        }
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
    ("POST", "/api/cap/stop-replication"): cap_stop_replication,
    ("POST", "/api/cap/start-replication"): cap_start_replication,
    ("POST", "/api/cap/test-divergence"): cap_test_divergence,
    ("POST", "/api/views/create"): views_create,
    ("POST", "/api/views/drop"): views_drop,
    ("POST", "/api/views/query-join"): views_query_join,
    ("POST", "/api/views/query-view"): views_query_view,
    ("POST", "/api/views/refresh"): views_refresh,
    ("POST", "/api/vertical/set-buffer"): vertical_set_buffer,
    ("POST", "/api/vertical/benchmark"): vertical_benchmark,
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
