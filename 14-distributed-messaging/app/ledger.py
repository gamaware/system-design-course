"""The payment ledger: what a customer was actually charged.

    python ledger.py           # show charges per order and flag double charges
    python ledger.py --reset   # empty the ledger before an experiment
"""

import argparse
import os
import sqlite3

LEDGER_PATH = os.environ.get("LEDGER_PATH", "/data/ledger.db")


def open_ledger():
    db = sqlite3.connect(LEDGER_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS charges (order_id TEXT, amount REAL, message_id TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS processed_messages (message_id TEXT PRIMARY KEY)")
    return db


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete every charge and processed ID")
    args = parser.parse_args()

    db = open_ledger()
    if args.reset:
        with db:
            db.execute("DELETE FROM charges")
            db.execute("DELETE FROM processed_messages")
        print("Ledger is empty.")
        return

    rows = db.execute(
        "SELECT order_id, COUNT(*), SUM(amount) FROM charges GROUP BY order_id ORDER BY order_id"
    ).fetchall()
    print(f"{'order':<10} {'charges':>7} {'charged':>9}")
    for order_id, count, total in rows:
        flag = "  <-- DOUBLE CHARGE" if count > 1 else ""
        print(f"{order_id:<10} {count:>7} {total:>9.2f}{flag}")
    charges = sum(row[1] for row in rows)
    print(f"{len(rows)} order(s), {charges} charge(s)")


if __name__ == "__main__":
    main()
