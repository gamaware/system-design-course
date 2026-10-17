"""Payment consumer: charges each order in a ledger (an SQLite database) and acknowledges it.

The flags reproduce the failure that matters in messaging: the process dies between doing the work
and telling the broker it did the work.

    --crash after-charge   charge, then die before the ack     -> the broker delivers it again
    --crash before-charge  die as soon as the message arrives  -> nothing was charged yet
    --ack-mode auto        the broker forgets the message the moment it sends it (at-most-once)
    --idempotent           remember processed message IDs and skip the ones already seen

Without --crash the consumer drains the queue and exits once it has been idle for two seconds.
"""

import argparse
import json
import os
import sqlite3

import broker
import ledger

IDLE_SECONDS = 2


def charge(db, order, message_id, idempotent):
    """Record the charge. Returns False when the message was already processed (duplicate)."""
    with db:  # one transaction: the charge and the processed-ID record commit together or not at all
        if idempotent:
            try:
                db.execute("INSERT INTO processed_messages (message_id) VALUES (?)", (message_id,))
            except sqlite3.IntegrityError:
                return False
        db.execute(
            "INSERT INTO charges (order_id, amount, message_id) VALUES (?, ?, ?)",
            (order["order_id"], order["amount"], message_id),
        )
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ack-mode", choices=["manual", "auto"], default="manual")
    parser.add_argument("--crash", choices=["none", "before-charge", "after-charge"], default="none")
    parser.add_argument("--idempotent", action="store_true")
    args = parser.parse_args()

    db = ledger.open_ledger()
    connection = broker.connect()
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)
    auto_ack = args.ack_mode == "auto"
    print(f"payment consumer: ack-mode={args.ack_mode} crash={args.crash} idempotent={args.idempotent}")

    stream = channel.consume(broker.PAYMENTS_QUEUE, auto_ack=auto_ack, inactivity_timeout=IDLE_SECONDS)
    for method, properties, body in stream:
        if method is None:
            break
        order = json.loads(body)
        print(f"  received {order['order_id']} (message_id={properties.message_id}, redelivered={method.redelivered})")
        if args.crash == "before-charge":
            print("  CRASH before charging. The process dies now.", flush=True)
            os._exit(1)  # simulate kill -9: no cleanup, no ack, the TCP connection just drops

        if charge(db, order, properties.message_id, args.idempotent):
            print(f"  charged {order['order_id']} ${order['amount']:.2f}")
        else:
            print(f"  duplicate {properties.message_id}: already charged, acknowledging without charging again")

        if args.crash == "after-charge":
            print("  CRASH after charging, before the ack. The process dies now.", flush=True)
            os._exit(1)
        if not auto_ack:
            channel.basic_ack(method.delivery_tag)

    connection.close()
    print("payment consumer: queue drained, exiting")


if __name__ == "__main__":
    main()
