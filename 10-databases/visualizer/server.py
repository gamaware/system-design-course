"""Database scalability visualizer API bridge — MySQL primary-replica."""

import ipaddress
import json
import os
import random
import threading
import time
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit

import pymysql

PRIMARY_HOST = os.environ.get("MYSQL_PRIMARY_HOST", "mysql-primary")
REPLICA_HOST = os.environ.get("MYSQL_REPLICA_HOST", "mysql-replica")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASS = os.environ.get("MYSQL_PASS", "rootpass")
MYSQL_DB = os.environ.get("MYSQL_DB", "university")

# Demo-data generator for the benchmark tab. The values are not secrets, but
# SystemRandom keeps the OS entropy source so no PRNG seed is ever involved.
_rng = random.SystemRandom()

# innodb_buffer_pool_size bounds accepted by the vertical scaling tab (bytes).
BUFFER_POOL_MIN = 16 * 1024 * 1024
BUFFER_POOL_MAX = 1024 * 1024 * 1024
BUFFER_POOL_DEFAULT = 128 * 1024 * 1024
BUFFER_RESIZE_TIMEOUT_S = 30

# Replica reads are retried every 5 ms until the row shows up or time runs out.
REPLICA_POLL_S = 0.005
REPLICA_WAIT_S = 1.5
CAP_REPLICA_WAIT_S = 1.0

# Benchmark table (~72 MB): larger than the small buffer pools, smaller than 128 MB.
BENCH_ROWS = 300000
BENCH_RANGE = 500
BENCH_SQL = "SELECT COUNT(*), MAX(payload) FROM bench_data WHERE id BETWEEN %s AND %s + 500"
BENCH_WARMUP_SQL = "SELECT SUM(LENGTH(payload)) FROM bench_data"

# The JOIN query and the materialized view share one definition, so the view
# holds exactly what the JOIN computes on every read.
VIEW_SELECT_SQL = (
    "SELECT s.name, s.major, c.code, c.title, e.enrolled_at, "
    "COALESCE(a.accesses, 0) AS accesses "
    "FROM enrollments e "
    "JOIN students s ON e.student_id = s.student_id "
    "JOIN courses c ON e.course_id = c.course_id "
    "LEFT JOIN (SELECT student_id, COUNT(*) AS accesses "
    "FROM access_log GROUP BY student_id) a ON a.student_id = e.student_id"
)
VIEW_TABLE_ALIASES = {"e": "enrollments", "s": "students", "c": "courses"}
JOIN_QUERY_SQL = VIEW_SELECT_SQL + " ORDER BY s.name, c.code"
VIEW_QUERY_SQL = ("SELECT name, major, code, title, enrolled_at, accesses "
                  "FROM enrollment_summary ORDER BY name, code")


def get_conn(host):
    """Return a MySQL connection to the specified host."""
    return pymysql.connect(
        host=host, user=MYSQL_USER, password=MYSQL_PASS,
        database=MYSQL_DB, cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def render_sql(cur, query, args):
    """Return the exact statement the driver sends for a parameterised query.

    The visualizer shows every statement in its SQL console. Rendering the
    display string through the driver (instead of formatting it by hand)
    guarantees the console shows the same escaped SQL that was executed.
    """
    return cur.mogrify(query, args)


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


def poll_for_row(cur, query, args, timeout_s):
    """Run a SELECT until it returns a row or timeout_s passes.

    Returns (row, reads, first_read_ms, waited_ms).
    """
    start = time.perf_counter()
    reads = 0
    first_ms = None
    while True:
        cur.execute(query, args)
        row = cur.fetchone()
        reads += 1
        waited = time.perf_counter() - start
        if first_ms is None:
            first_ms = waited * 1000
        if row is not None or waited >= timeout_s:
            return row, reads, first_ms, waited * 1000
        time.sleep(REPLICA_POLL_S)


def replica_running(status):
    """True when SHOW REPLICA STATUS says the replica is applying changes."""
    return bool(status) and status.get("Replica_SQL_Running") == "Yes" \
        and status.get("Replica_IO_Running") != "No"


# ---- Replication Tab ----

def replication_write(body):
    """Insert a student on the primary and read from replica."""
    name = body.get("name", "Test Student")
    email = body.get("email", "test@university.edu")
    major = body.get("major", "Computer Science")
    steps = []
    total_start = time.perf_counter()
    seq = 1

    insert_query = "INSERT INTO students (name, email, major) VALUES (%s, %s, %s)"
    insert_args = (name, email, major)
    conn = get_conn(PRIMARY_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(insert_query, insert_args)
            new_id = cur.lastrowid
            t1 = time.perf_counter()
            committed_at = t1
            insert_sql = render_sql(cur, insert_query, insert_args)
        steps.append(step_entry(seq, "INSERT", "primary", "OK",
                                (t1 - t0) * 1000, {"student_id": new_id},
                                sql=insert_sql))
        seq += 1
    finally:
        conn.close()

    select_query = "SELECT * FROM students WHERE student_id = %s"
    conn = get_conn(REPLICA_HOST)
    try:
        with conn.cursor() as cur:
            select_sql = render_sql(cur, select_query, (new_id,))
            row, reads, first_ms, waited_ms = poll_for_row(
                cur, select_query, (new_id,), REPLICA_WAIT_S)
        # Time from the primary commit until the replica returned the row. It
        # includes the replica connection setup, so it is an upper bound.
        found = row is not None
        lag_ms = round((time.perf_counter() - committed_at) * 1000, 1)
        if reads == 1:
            steps.append(step_entry(seq, "SELECT", "replica",
                                    "FOUND" if found else "NOT YET REPLICATED",
                                    first_ms, row, sql=select_sql))
        else:
            # First read missed: show it, then the read that ended the wait.
            steps.append(step_entry(seq, "SELECT", "replica", "NOT YET REPLICATED",
                                    first_ms, sql=select_sql))
            seq += 1
            steps.append(step_entry(
                seq, f"SELECT (read {reads})", "replica",
                "FOUND" if found else "NOT YET REPLICATED", waited_ms,
                {"reads": reads, "visible_after_commit_ms": lag_ms, "row": row}, sql=select_sql,
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
    if found and reads == 1:
        interp = (f"The row was already on the replica at the first read, at most "
                  f"{lag_ms}ms after the commit on the primary. "
                  f"Seconds_Behind_Source is {lag}; it counts whole "
                  "seconds, so sub-second lag shows as 0. Sending SELECTs to replicas "
                  "takes load off the primary -- this is horizontal read scaling. The "
                  "trade-off: during lag spikes a replica serves slightly stale data.")
    elif found:
        interp = (f"The first read missed: the row appeared on the replica at most "
                  f"{lag_ms}ms after the commit on the primary ({reads} reads, one every "
                  f"{round(REPLICA_POLL_S * 1000)}ms). "
                  "That window is the replication lag. Any application reading from "
                  "replicas must tolerate this short window of stale data.")
    else:
        interp = (f"The row was still NOT on the replica after {REPLICA_WAIT_S}s "
                  f"({reads} reads). "
                  "Replication is stopped or far behind (check the IO and SQL threads "
                  "in the sidebar). Applications reading from replicas must tolerate "
                  "eventual consistency: the data arrives only once replication catches up.")
    return {"pattern": "replication", "steps": steps, "total_ms": round(total_ms, 2),
            "replicated": found, "replication_lag_ms": lag_ms if found else None,
            "replica_reads": reads, "interpretation": interp}


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
            delete_query = "DELETE FROM enrollments WHERE student_id = %s AND course_id = %s"
            delete_sql = render_sql(cur, delete_query, (student_id, from_id))
            t0 = time.perf_counter()
            cur.execute(delete_query, (student_id, from_id))
            affected = cur.rowcount
            t1 = time.perf_counter()
            steps.append(step_entry(seq, f"DELETE enrollment ({from_course})", "primary",
                                    "OK" if affected > 0 else "NOT ENROLLED",
                                    (t1 - t0) * 1000, {"rows_affected": affected},
                                    sql=delete_sql))
            seq += 1

            if affected == 0:
                t0 = time.perf_counter()
                conn.rollback()
                t1 = time.perf_counter()
                steps.append(step_entry(seq, "ROLLBACK", "primary", "OK",
                                        (t1 - t0) * 1000, sql="ROLLBACK"))
                total_ms = (time.perf_counter() - total_start) * 1000
                return {"pattern": "consistency", "steps": steps,
                        "total_ms": round(total_ms, 2), "outcome": "ROLLED BACK",
                        "interpretation": (
                            f"Student {student_id} is not enrolled in {from_course}, "
                            f"so the DELETE matched 0 rows. The transfer stopped there "
                            f"and the transaction was ROLLED BACK: no enrollment or "
                            f"count changed. Without this check the UPDATE would "
                            f"decrement {from_course} for a student who was never in "
                            f"it, and the counts would drift from the real "
                            f"enrollments.")}

            # Update from-course count
            update_from_query = ("UPDATE courses SET enrolled = enrolled - 1 "
                                 "WHERE course_id = %s AND enrolled > 0")
            update_from_sql = render_sql(cur, update_from_query, (from_id,))
            t0 = time.perf_counter()
            cur.execute(update_from_query, (from_id,))
            t1 = time.perf_counter()
            steps.append(step_entry(seq, f"UPDATE {from_course} enrolled-1", "primary", "OK",
                                    (t1 - t0) * 1000,
                                    sql=update_from_sql))
            seq += 1

            # Insert new enrollment
            insert_query = "INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s)"
            insert_sql = render_sql(cur, insert_query, (student_id, to_id))
            t0 = time.perf_counter()
            try:
                cur.execute(insert_query, (student_id, to_id))
                t1 = time.perf_counter()
                steps.append(step_entry(seq, f"INSERT enrollment ({to_course})", "primary", "OK",
                                        (t1 - t0) * 1000, sql=insert_sql))
            except pymysql.IntegrityError as exc:
                t1 = time.perf_counter()
                steps.append(step_entry(seq, f"INSERT enrollment ({to_course})", "primary",
                                        "CONSTRAINT VIOLATION", (t1 - t0) * 1000,
                                        {"error": str(exc)}, sql=insert_sql))
                t0 = time.perf_counter()
                conn.rollback()
                t1 = time.perf_counter()
                steps.append(step_entry(seq + 1, "ROLLBACK", "primary", "OK",
                                        (t1 - t0) * 1000, sql="ROLLBACK"))
                total_ms = (time.perf_counter() - total_start) * 1000
                return {"pattern": "consistency", "steps": steps,
                        "total_ms": round(total_ms, 2), "outcome": "ROLLED BACK",
                        "interpretation": (
                            f"The INSERT failed: student {student_id} is already "
                            f"enrolled in {to_course} (unique constraint). The "
                            f"transaction was ROLLED BACK, so the DELETE and the "
                            f"{from_course} count decrement that had already run were "
                            f"undone too. This is atomicity: the database is left "
                            f"exactly as if the transfer was never attempted.")}
            seq += 1

            # Update to-course count
            update_to_query = "UPDATE courses SET enrolled = enrolled + 1 WHERE course_id = %s"
            update_to_sql = render_sql(cur, update_to_query, (to_id,))
            t0 = time.perf_counter()
            cur.execute(update_to_query, (to_id,))
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

    explain_query = "EXPLAIN SELECT * FROM access_log WHERE student_id = %s AND resource = %s"
    count_query = "SELECT COUNT(*) AS cnt FROM access_log WHERE student_id = %s AND resource = %s"
    args = (student_id, resource)

    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            # Run EXPLAIN
            t0 = time.perf_counter()
            cur.execute(explain_query, args)
            plan = cur.fetchone()
            t1 = time.perf_counter()
            explain_sql = render_sql(cur, explain_query, args)
            steps.append(step_entry(seq, "EXPLAIN", "primary", "OK",
                                    (t1 - t0) * 1000, plan, sql=explain_sql))
            seq += 1

            # Run actual query with timing
            t0 = time.perf_counter()
            cur.execute(count_query, args)
            result = cur.fetchone()
            t1 = time.perf_counter()
            count_sql = render_sql(cur, count_query, args)
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
            interp = (f"No index is used: MySQL scans the whole table (type {scan_type}), "
                      f"examining ~{rows_scanned} rows. Every row must be read, which "
                      f"gets slower as the table grows. Adding a composite index on "
                      f"(student_id, resource) would reduce this to a few rows.")

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "schema", "steps": steps, "total_ms": round(total_ms, 2),
                "interpretation": interp}
    finally:
        conn.close()


INDEX_NAME = "idx_student_resource"
CREATE_INDEX_SQL = f"CREATE INDEX {INDEX_NAME} ON access_log (student_id, resource)"
DROP_INDEX_SQL = f"DROP INDEX {INDEX_NAME} ON access_log"
ANALYZE_SQL = "ANALYZE TABLE access_log"


def analyze_access_log(cur, seq):
    """Refresh access_log statistics so EXPLAIN row estimates stay accurate."""
    t0 = time.perf_counter()
    cur.execute(ANALYZE_SQL)
    cur.fetchall()
    t1 = time.perf_counter()
    return step_entry(seq, "ANALYZE TABLE", "primary", "OK", (t1 - t0) * 1000,
                      sql=ANALYZE_SQL)


def schema_index_change(statement, action, done, skipped):
    """Create or drop the composite index, then refresh table statistics."""
    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            try:
                cur.execute(statement)
                result = done
            except pymysql.err.OperationalError:
                result = skipped
            t1 = time.perf_counter()
            steps = [step_entry(1, action, "primary", result, (t1 - t0) * 1000,
                                sql=statement),
                     analyze_access_log(cur, 2)]
        return {"action": action, "result": result, "index": INDEX_NAME,
                "latency_ms": round(sum(st["latency_ms"] for st in steps), 2),
                "sql": statement, "steps": steps}
    finally:
        conn.close()


def schema_add_index(_body):
    """Add composite index on access_log."""
    return schema_index_change(CREATE_INDEX_SQL, "CREATE INDEX", "CREATED", "ALREADY EXISTS")


def schema_drop_index(_body):
    """Drop the composite index."""
    return schema_index_change(DROP_INDEX_SQL, "DROP INDEX", "DROPPED", "NOT FOUND")


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


RESET_STATEMENTS = (
    ("DELETE enrollments", "DELETE FROM enrollments"),
    ("DELETE added students", "DELETE FROM students WHERE student_id > 10"),
    ("DELETE added courses",
     "DELETE FROM courses WHERE code NOT IN ('CS101','CS201','MATH101','PHYS101')"),
    ("RESET course counts",
     "UPDATE courses SET enrolled = CASE code WHEN 'CS101' THEN 4 WHEN 'CS201' THEN 2 "
     "WHEN 'MATH101' THEN 2 WHEN 'PHYS101' THEN 2 END"),
    ("INSERT original enrollments",
     "INSERT INTO enrollments (student_id, course_id) VALUES "
     "(1,1),(3,1),(5,1),(8,1),(1,2),(3,2),(2,3),(6,3),(4,4),(9,4)"),
    ("DELETE added access_log rows", "DELETE FROM access_log WHERE log_id > 10000"),
    ("DROP materialized view", "DROP TABLE IF EXISTS enrollment_summary"),
)
REPLICA_SYNC_TIMEOUT_S = 30


def db_reset(_body):
    """Reset database to initial state."""
    steps = []
    problems = []
    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            for label, statement in RESET_STATEMENTS:
                t0 = time.perf_counter()
                cur.execute(statement)
                t1 = time.perf_counter()
                steps.append(step_entry(len(steps) + 1, label, "primary", "OK",
                                        (t1 - t0) * 1000, sql=statement))
            t0 = time.perf_counter()
            try:
                cur.execute(DROP_INDEX_SQL)
                index_result = "DROPPED"
            except pymysql.err.OperationalError:
                index_result = "NO INDEX"
            t1 = time.perf_counter()
            steps.append(step_entry(len(steps) + 1, "DROP INDEX", "primary", index_result,
                                    (t1 - t0) * 1000, sql=DROP_INDEX_SQL))
            steps.append(analyze_access_log(cur, len(steps) + 1))
            cur.execute("SELECT @@GLOBAL.gtid_executed AS gtids")
            primary_gtids = cur.fetchone()["gtids"]

        pool = set_buffer_pool(conn, BUFFER_POOL_DEFAULT)
        steps.append(step_entry(len(steps) + 1, "SET BUFFER POOL 128 MB", "primary",
                                "OK" if pool["actual"] == BUFFER_POOL_DEFAULT else "ERROR",
                                pool["latency_ms"], sql=pool["sql"]))
        if pool["actual"] != BUFFER_POOL_DEFAULT:
            problems.append(f"buffer pool is {pool['actual'] // (1024 * 1024)} MB, not 128 MB")
    finally:
        conn.close()

    conn = get_conn(REPLICA_HOST)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW REPLICA STATUS")
            status = cur.fetchone()
            if status and not replica_running(status):
                t0 = time.perf_counter()
                cur.execute("START REPLICA")
                deadline = time.monotonic() + REPLICA_SYNC_TIMEOUT_S
                while time.monotonic() < deadline:
                    cur.execute("SHOW REPLICA STATUS")
                    status = cur.fetchone()
                    if status.get("Replica_IO_Running") == "Yes" and \
                            status.get("Replica_SQL_Running") == "Yes":
                        break
                    time.sleep(0.2)
                t1 = time.perf_counter()
                running = status.get("Replica_IO_Running") == "Yes" and \
                    status.get("Replica_SQL_Running") == "Yes"
                steps.append(step_entry(len(steps) + 1, "START REPLICA", "replica",
                                        "OK" if running else "NOT RUNNING",
                                        (t1 - t0) * 1000, sql="START REPLICA"))
                if not running:
                    problems.append("replication did not restart")
            if replica_running(status):
                # Wait until the replica has applied every reset statement.
                wait_query = "SELECT WAIT_FOR_EXECUTED_GTID_SET(%s, %s) AS timed_out"
                wait_args = (primary_gtids, REPLICA_SYNC_TIMEOUT_S)
                t0 = time.perf_counter()
                cur.execute(wait_query, wait_args)
                timed_out = cur.fetchone()["timed_out"]
                t1 = time.perf_counter()
                steps.append(step_entry(len(steps) + 1, "WAIT FOR REPLICA", "replica",
                                        "IN SYNC" if timed_out == 0 else "NOT IN SYNC",
                                        (t1 - t0) * 1000,
                                        sql=render_sql(cur, wait_query, wait_args)))
                if timed_out != 0:
                    problems.append("the replica has not caught up yet")
    finally:
        conn.close()

    if problems:
        return {"result": "INCOMPLETE", "steps": steps,
                "message": "Database reset, but " + "; ".join(problems) + "."}
    return {"result": "OK", "steps": steps,
            "message": "Database reset to initial state"}


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

    # The mysql client's \G suffix is not SQL: strip it and ask the UI to
    # print the rows vertically, the way the client does.
    query = query.rstrip(";").rstrip()
    vertical = query.endswith("\\G")
    if vertical:
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
                    "target": target, "query": query, "vertical": vertical,
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
    email = f"cap-{uuid.uuid4().hex[:8]}@university.edu"
    steps = []
    total_start = time.perf_counter()
    seq = 1

    # Write to primary
    insert_query = "INSERT INTO students (name, email, major) VALUES (%s, %s, 'CAP Test')"
    conn = get_conn(PRIMARY_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(insert_query, (name, email))
            new_id = cur.lastrowid
            t1 = time.perf_counter()
            insert_sql = render_sql(cur, insert_query, (name, email))
        steps.append(step_entry(seq, "INSERT", "primary", "OK",
                                (t1 - t0) * 1000, {"student_id": new_id},
                                sql=insert_sql))
        seq += 1
    finally:
        conn.close()

    # Read from primary (should always have it)
    select_query = "SELECT * FROM students WHERE student_id = %s"
    conn = get_conn(PRIMARY_HOST)
    try:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(select_query, (new_id,))
            row = cur.fetchone()
            t1 = time.perf_counter()
            select_sql = render_sql(cur, select_query, (new_id,))
        primary_found = row is not None
        steps.append(step_entry(seq, "SELECT (primary)", "primary",
                                "FOUND" if primary_found else "NOT FOUND",
                                (t1 - t0) * 1000, row, sql=select_sql))
        seq += 1
    finally:
        conn.close()

    # Read from replica: wait briefly for replication when it is running,
    # read once when it is stopped (the partition).
    conn = get_conn(REPLICA_HOST)
    try:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute("SHOW REPLICA STATUS")
            running = replica_running(cur.fetchone())
            t1 = time.perf_counter()
            steps.append(step_entry(seq, "SHOW REPLICA STATUS", "replica",
                                    "REPLICATION RUNNING" if running else "REPLICATION STOPPED",
                                    (t1 - t0) * 1000, sql="SHOW REPLICA STATUS"))
            seq += 1
            row, reads, _, waited_ms = poll_for_row(
                cur, select_query, (new_id,), CAP_REPLICA_WAIT_S if running else 0)
        replica_found = row is not None
        steps.append(step_entry(seq, "SELECT (replica)", "replica",
                                "FOUND (consistent)" if replica_found else "NOT FOUND (stale)",
                                waited_ms, {"reads": reads, "row": row}, sql=select_sql))
    finally:
        conn.close()

    total_ms = (time.perf_counter() - total_start) * 1000
    diverged = primary_found != replica_found
    if diverged and not running:
        outcome = "DIVERGED (partition active)"
        interp = ("The primary and replica returned different results -- the nodes "
                  "have DIVERGED. Replication is stopped, so the write stayed on the "
                  "primary. During a partition, reading the replica keeps the system "
                  "available but returns stale data (AP); reading only the primary "
                  "keeps it consistent (CP).")
    elif diverged:
        outcome = "DIVERGED (replica lagging)"
        interp = (f"Replication is running, but the replica still did not have the row "
                  f"after {CAP_REPLICA_WAIT_S}s ({reads} reads). It is lagging behind the "
                  "primary: until it catches up, replica reads return stale data.")
    else:
        outcome = "CONSISTENT"
        interp = (f"Both nodes returned the row -- the system is CONSISTENT. With "
                  f"replication running, the replica had it after "
                  f"{round(waited_ms, 1)}ms ({reads} read{'s' if reads > 1 else ''}). "
                  "No partition, so no trade-off between consistency and availability "
                  "is needed.")
    return {
        "pattern": "cap", "steps": steps, "total_ms": round(total_ms, 2),
        "outcome": outcome, "interpretation": interp,
    }


# ---- Materialized Views Tab ----

def views_create(_body):
    """Create a materialized view (table from SELECT) for enrollment summary."""
    create_sql = "CREATE TABLE enrollment_summary AS " + VIEW_SELECT_SQL
    conn = get_conn(PRIMARY_HOST)
    try:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute("DROP TABLE IF EXISTS enrollment_summary")
            cur.execute(create_sql)
            cur.execute("SELECT COUNT(*) AS cnt FROM enrollment_summary")
            cnt = cur.fetchone()["cnt"]
            t1 = time.perf_counter()
        return {"action": "CREATE VIEW", "result": "CREATED",
                "rows": cnt, "latency_ms": round((t1 - t0) * 1000, 2),
                "sql": create_sql,
                "steps": [step_entry(1, "CREATE TABLE enrollment_summary", "primary",
                                     "CREATED", (t1 - t0) * 1000, sql=create_sql)],
                "interpretation": (
                    f"Pre-computed {cnt} rows into a flat table: the JOIN of "
                    f"enrollments, students and courses plus the per-student "
                    f"access count from access_log ran once, now. Future reads hit "
                    f"this single table instead of recomputing it every time -- a "
                    f"classic space-for-time trade-off.")}
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
    """Run the view's defining query (JOINs + access count) with timing."""
    conn = get_conn(PRIMARY_HOST)
    try:
        steps = []
        total_start = time.perf_counter()

        with conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute(JOIN_QUERY_SQL)
            rows = cur.fetchall()
            t1 = time.perf_counter()
            query_ms = (t1 - t0) * 1000
            steps.append(step_entry(1, "SELECT with JOINs + COUNT", "primary",
                                    "OK", query_ms,
                                    {"row_count": len(rows)}, sql=JOIN_QUERY_SQL))

            explain_sql = "EXPLAIN " + VIEW_SELECT_SQL
            t0 = time.perf_counter()
            cur.execute(explain_sql)
            plan = cur.fetchall()
            t1 = time.perf_counter()
            # EXPLAIN lists aliases, and the GROUP BY subquery as <derived2>:
            # count only base tables, by their real names.
            tables = sorted({VIEW_TABLE_ALIASES.get(p["table"], p["table"]) for p in plan
                             if p.get("table") and not p["table"].startswith("<")})
            steps.append(step_entry(2, "EXPLAIN (tables scanned)", "primary",
                                    f"{len(tables)} tables", (t1 - t0) * 1000,
                                    {"tables": tables}, sql=explain_sql))

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "views-join", "steps": steps,
                "total_ms": round(total_ms, 2), "query_ms": round(query_ms, 2),
                "row_count": len(rows), "rows": rows,
                "interpretation": (
                    f"The query read {len(tables)} tables ({', '.join(tables)}) and "
                    f"counted every access_log row per student to produce "
                    f"{len(rows)} rows in {round(query_ms, 2)}ms. It recomputes all "
                    f"of that on every read, so the result is always current. "
                    f"Compare with Query from View.")}
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
            cur.execute(VIEW_QUERY_SQL)
            rows = cur.fetchall()
            t1 = time.perf_counter()
            query_ms = (t1 - t0) * 1000
            steps.append(step_entry(1, "SELECT from materialized view", "primary",
                                    "OK", query_ms,
                                    {"row_count": len(rows)}, sql=VIEW_QUERY_SQL))

        total_ms = (time.perf_counter() - total_start) * 1000
        return {"pattern": "views-view", "steps": steps,
                "total_ms": round(total_ms, 2), "query_ms": round(query_ms, 2),
                "row_count": len(rows), "rows": rows,
                "interpretation": (
                    f"Reading {len(rows)} rows from the pre-computed table took "
                    f"{round(query_ms, 2)}ms -- no joins and no counting. Compare "
                    f"this with Query with JOINs. The trade-off: the table is a "
                    f"snapshot from the last Create or Refresh, so changes made "
                    f"since then do not appear until you refresh it.")}
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

def buffer_pool_state(cur):
    """Return (resize_status_code, real pool size in bytes)."""
    cur.execute("SHOW GLOBAL STATUS WHERE Variable_name IN "
                "('Innodb_buffer_pool_resize_status_code', 'Innodb_buffer_pool_pages_total')")
    status = {r["Variable_name"]: int(r["Value"]) for r in cur.fetchall()}
    cur.execute("SELECT @@innodb_page_size AS page")
    page = int(cur.fetchone()["page"])
    return (status["Innodb_buffer_pool_resize_status_code"],
            status["Innodb_buffer_pool_pages_total"] * page)


def set_buffer_pool(conn, size):
    """Resize the buffer pool and wait for InnoDB to finish.

    @@innodb_buffer_pool_size changes as soon as SET GLOBAL returns, while the
    resize runs in the background; the page count shows the real size.
    """
    # MySQL does not accept server-side bind parameters in SET GLOBAL. pymysql
    # interpolates %s on the client, so callers must pass a validated int.
    set_query = "SET GLOBAL innodb_buffer_pool_size = %s"
    with conn.cursor() as cur:
        _, before = buffer_pool_state(cur)
        t0 = time.perf_counter()
        cur.execute(set_query, (size,))
        set_sql = render_sql(cur, set_query, (size,))
        deadline = time.monotonic() + BUFFER_RESIZE_TIMEOUT_S
        settle = time.monotonic() + 2
        while True:
            code, actual = buffer_pool_state(cur)
            now = time.monotonic()
            if code == 0 and (actual == size or now > settle):
                break
            if now > deadline:
                break
            time.sleep(0.1)
        t1 = time.perf_counter()
    return {"before": before, "actual": actual, "in_progress": code != 0,
            "latency_ms": round((t1 - t0) * 1000, 2), "sql": set_sql}


# Two browsers can click Set Buffer or Run Benchmark at once; only one may build.
_BENCH_LOCK = threading.Lock()


def ensure_bench_data(conn):
    """Create the benchmark table on the primary if it does not exist yet.

    Returns a step entry when the table was created, else None.
    """
    with _BENCH_LOCK:
        return _build_bench_data(conn)


def _build_bench_data(conn):
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE 'bench_data'")
        if cur.fetchone():
            return None
    build_query = ("INSERT INTO bench_data_build (id, student_id, payload) "
                   "WITH RECURSIVE seq (n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM seq "
                   "WHERE n < %s) "
                   "SELECT n, 1 + n %% 10, REPEAT('x', 200) FROM seq")
    build = get_conn(PRIMARY_HOST)
    try:
        with build.cursor() as cur:
            t0 = time.perf_counter()
            # Local benchmark data: keep it out of the binlog (not replicated).
            cur.execute("SET SESSION sql_log_bin = 0")
            cur.execute("SET SESSION cte_max_recursion_depth = %s", (BENCH_ROWS + 1,))
            cur.execute("DROP TABLE IF EXISTS bench_data_build")
            cur.execute("CREATE TABLE bench_data_build (id INT PRIMARY KEY, "
                        "student_id INT NOT NULL, payload CHAR(200) NOT NULL)")
            cur.execute(build_query, (BENCH_ROWS,))
            build_sql = render_sql(cur, build_query, (BENCH_ROWS,))
            # Rename last, so bench_data only ever exists complete.
            cur.execute("RENAME TABLE bench_data_build TO bench_data")
            # Fresh statistics still say "26 rows", which makes the optimizer
            # pick a full scan over the primary-key range.
            cur.execute("ANALYZE TABLE bench_data")
            cur.fetchall()
            t1 = time.perf_counter()
    finally:
        build.close()
    return step_entry(1, f"CREATE bench_data ({BENCH_ROWS:,} rows)", "primary", "CREATED",
                      (t1 - t0) * 1000, sql=build_sql.replace("bench_data_build", "bench_data"))


def vertical_set_buffer(body):
    """Set InnoDB buffer pool size (bytes, within the lab's safe range)."""
    try:
        size = int(body.get("size", 64 * 1024 * 1024))
    except (TypeError, ValueError, OverflowError):
        return {"error": "size must be an integer number of bytes"}
    if not BUFFER_POOL_MIN <= size <= BUFFER_POOL_MAX:
        return {"error": f"size must be between {BUFFER_POOL_MIN} and {BUFFER_POOL_MAX} bytes"}

    mb = 1024 * 1024
    conn = get_conn(PRIMARY_HOST)
    try:
        steps = []
        created = ensure_bench_data(conn)
        if created:
            steps.append(created)
        pool = set_buffer_pool(conn, size)
        ok = pool["actual"] == size
        steps.append(step_entry(len(steps) + 1, "SET GLOBAL innodb_buffer_pool_size",
                                "primary", "OK" if ok else "ERROR", pool["latency_ms"],
                                sql=pool["sql"]))
        result = {"action": "SET BUFFER POOL", "size": size, "actual_size": pool["actual"],
                  "previous_size": pool["before"], "latency_ms": pool["latency_ms"],
                  "sql": pool["sql"], "steps": steps}
        before_mb, actual_mb = pool["before"] // mb, pool["actual"] // mb
        if not ok:
            state = "is still resizing" if pool["in_progress"] else "did not resize"
            result["error"] = (f"Requested {size // mb} MB, but the buffer pool {state}: "
                               f"it is {actual_mb} MB now. Wait a few seconds and try again.")
            return result
        if actual_mb > before_mb:
            result["interpretation"] = (
                f"Buffer pool grew from {before_mb} MB to {actual_mb} MB. More data pages "
                f"now fit in memory, so fewer reads have to go to disk -- this is "
                f"vertical scaling. Run the benchmark to measure the effect.")
        elif actual_mb < before_mb:
            result["interpretation"] = (
                f"Buffer pool shrank from {before_mb} MB to {actual_mb} MB. Fewer data "
                f"pages fit in memory, so more reads will have to go to disk. Run the "
                f"benchmark to measure the effect.")
        else:
            result["interpretation"] = (
                f"The buffer pool was already {actual_mb} MB, so nothing changed. "
                f"Pick another size to compare.")
        return result
    except pymysql.MySQLError as exc:
        return {"error": str(exc)}
    finally:
        conn.close()


def read_buffer_counters(cur):
    """Return (logical read requests, reads that went to disk) since startup."""
    cur.execute("SHOW GLOBAL STATUS WHERE Variable_name IN "
                "('Innodb_buffer_pool_read_requests', 'Innodb_buffer_pool_reads')")
    status = {r["Variable_name"]: int(r["Value"]) for r in cur.fetchall()}
    return status["Innodb_buffer_pool_read_requests"], status["Innodb_buffer_pool_reads"]


def vertical_benchmark(body):
    """Run random range queries on bench_data and measure the buffer hit ratio."""
    count = int(body.get("count", 200))
    if not 1 <= count <= 2000:
        return {"error": "count must be between 1 and 2000"}
    conn = get_conn(PRIMARY_HOST)
    try:
        total_start = time.perf_counter()
        steps = []
        created = ensure_bench_data(conn)
        if created:
            steps.append(created)

        latencies = []
        with conn.cursor() as cur:
            # One full scan first, so every run starts from the same warm cache.
            t0 = time.perf_counter()
            cur.execute(BENCH_WARMUP_SQL)
            cur.fetchall()
            t1 = time.perf_counter()
            steps.append(step_entry(len(steps) + 1, "Warm-up scan", "primary", "OK",
                                    (t1 - t0) * 1000, sql=BENCH_WARMUP_SQL))

            # Global counters cannot be reset (FLUSH STATUS leaves them alone),
            # so measure the difference across the run.
            requests_before, disk_before = read_buffer_counters(cur)
            starts = [_rng.randint(1, BENCH_ROWS - BENCH_RANGE) for _ in range(count)]
            bench_start = time.perf_counter()
            for start in starts:
                t0 = time.perf_counter()
                cur.execute(BENCH_SQL, (start, start))
                cur.fetchall()
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000)
            bench_s = time.perf_counter() - bench_start
            requests_after, disk_after = read_buffer_counters(cur)
            sample_sql = render_sql(cur, BENCH_SQL, (starts[0], starts[0]))
            steps.append(step_entry(len(steps) + 1, f"{count} x range SELECT", "primary",
                                    "OK", bench_s * 1000, sql=sample_sql))

            cur.execute("SELECT @@innodb_buffer_pool_size AS size")
            pool_size = cur.fetchone()["size"]

        read_requests = requests_after - requests_before
        disk_reads = disk_after - disk_before
        memory_reads = read_requests - disk_reads
        hit_ratio = round((1 - disk_reads / max(read_requests, 1)) * 100, 1)
        avg_latency = round(sum(latencies) / len(latencies), 2)
        p95 = round(sorted(latencies)[int(len(latencies) * 0.95)], 2)
        qps = round(count / bench_s, 1)

        if hit_ratio >= 99:
            interp = (f"Buffer hit ratio is {hit_ratio}% -- nearly all reads served "
                      f"from memory ({memory_reads} memory reads vs {disk_reads} "
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
            "sql": sample_sql, "steps": steps,
            "interpretation": interp,
            "stats": {
                "queries": count,
                "avg_latency_ms": avg_latency,
                "p95_latency_ms": p95,
                "queries_per_sec": qps,
                "buffer_pool_size": pool_size,
                "buffer_hit_ratio": hit_ratio,
                "disk_reads": disk_reads,
                "memory_reads": memory_reads,
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


def _is_direct_host(host):
    """True for localhost or an IP address, never a DNS name (blocks DNS rebinding)."""
    name = urlsplit(f"//{host}").hostname or ""
    if name == "localhost":
        return True
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


class Handler(SimpleHTTPRequestHandler):
    """HTTP request handler for the database visualizer.

    The UI and the API share one origin, so there are no CORS headers: other
    web pages the student opens must not be able to drive the root SQL console.
    """

    def _trusted_request(self):
        host = self.headers.get("Host", "")
        if not _is_direct_host(host):
            return False
        origin = self.headers.get("Origin")
        return origin is None or urlsplit(origin).netloc == host

    def do_GET(self):  # noqa: N802
        if not self._trusted_request():
            self._send_json({"error": "Forbidden"}, 403)
            return
        path = self.path.split("?")[0]
        handler = ROUTES.get(("GET", path))
        if handler:
            self._send_json(handler(None))
            return
        if path == "/":
            path = "/index.html"
        self._serve_static(path)

    def do_POST(self):  # noqa: N802
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip()
        if not self._trusted_request() or content_type != "application/json":
            self._send_json({"error": "Forbidden"}, 403)
            return
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
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()
