from dataclasses import dataclass
from threading import Lock
from .threadsafesocket import ThreadSafeSocket


@dataclass
class ConnectionRegistry:
    """
    The connection registry entry, which stores the
    connection object, the address, and the associated
    registry name.
    """
    name: str
    connection: ThreadSafeSocket


class ConnectionMap:

    def __init__(self):
        self.lock = Lock()
        self.inbound_connections: dict[str, ConnectionRegistry] = {}
        self.outbound_connections: dict[str, ConnectionRegistry] = {}

    def register(self, name, entry: ConnectionRegistry, inbound: bool):
        """
        Registers either an inbound or outbound connection.

        Returns:
            tuple[bool, bool]:
                - success: whether this direction was registered
                - first_for_peer: whether this was the first live
                  connection of any direction for this peer
        """
        print(f"Registering {'inbound' if inbound else 'outbound'} connection for {name}")
        with self.lock:
            table = self.inbound_connections if inbound else self.outbound_connections

            if name in table:
                return False, False

            existed_before = (
                name in self.inbound_connections or
                name in self.outbound_connections
            )

            table[name] = entry
            return True, not existed_before

    def has_inbound_connection(self, name: str):
        with self.lock:
            return name in self.inbound_connections

    def has_outbound_connection(self, name: str):
        with self.lock:
            return name in self.outbound_connections

    def has_connection(self, name: str):
        with self.lock:
            return (
                name in self.inbound_connections or
                name in self.outbound_connections
            )

    def deregister(self, target: str):
        """
        Hard-remove all connections for a target.
        """
        print(f'Deregistering connection for {target}')
        with self.lock:
            inbound = self.inbound_connections.pop(target, None)
            outbound = self.outbound_connections.pop(target, None)

        for entry in (inbound, outbound):
            if entry is not None:
                try:
                    entry.connection.close()
                except Exception:
                    pass

    def deregister_if_same(self, target: str, connection: ThreadSafeSocket) -> bool:
        """
        Removes whichever direction maps to the exact socket object.

        Returns:
            bool: True only if this removal caused the peer to have
            no remaining live inbound/outbound connections.
        """
        removed_any = False

        with self.lock:
            entry = self.inbound_connections.get(target)
            if entry is not None and entry.connection is connection:
                self.inbound_connections.pop(target, None)
                removed_any = True

            entry = self.outbound_connections.get(target)
            if entry is not None and entry.connection is connection:
                self.outbound_connections.pop(target, None)
                removed_any = True

            still_connected = (
                target in self.inbound_connections or
                target in self.outbound_connections
            )

        if removed_any:
            try:
                connection.close()
            except Exception:
                pass

        return removed_any and not still_connected

    def shutdown(self):
        with self.lock:
            all_entries = list(self.inbound_connections.values()) + list(self.outbound_connections.values())
            self.inbound_connections.clear()
            self.outbound_connections.clear()

        seen = set()
        for entry in all_entries:
            ident = id(entry.connection)
            if ident in seen:
                continue
            seen.add(ident)
            try:
                entry.connection.close()
            except Exception:
                pass

    def get_connection_names(self):
        with self.lock:
            return list(set(self.inbound_connections.keys()) | set(self.outbound_connections.keys()))

    def get_connection(self, name: str) -> ConnectionRegistry:
        """
        Prefer outbound for active sends, but fall back to inbound
        because the protocol is duplex.
        """
        with self.lock:
            if name in self.outbound_connections:
                return self.outbound_connections[name]
            if name in self.inbound_connections:
                return self.inbound_connections[name]
            raise KeyError(name)