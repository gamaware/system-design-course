"""Declare the lab topology once. setup.sh runs this; you can run it again at any time."""

import broker


def main():
    connection = broker.connect()
    broker.declare_topology(connection.channel())
    connection.close()
    print("Topology declared: exchanges, queues and bindings are in place.")


if __name__ == "__main__":
    main()
