# Distributed System: Replication Feature Documentation

## Overview
Replication ensures data consistency and availability across multiple nodes in the Distributed File System (DFS). This feature enhances fault tolerance by copying data files automatically between the primary server and configured cluster peers.

### Key Components of Replication
1. **Server-Side Logic: Primary Server (main2.py)**
   - Handles file uploads from clients.
   - Spawns threads to replicate files to peer servers.
   - Manages error handling during replication attempts.

2. **Peer Server Utility (peer_server.py)**
   - Monitors changes in the primary server.
   - Downloads updated/added files from the primary server and uploads them to other peers.
   - Deletes files as instructed by the primary server.

3. **Replica Launching Script (server-replica.sh)**
   - Automates the setup of multiple DFS server instances.
   - Configures unique storage paths and ports for each replica.


## Flow Description
Below is the flow for core replication operations:

### File Upload Replication
1. **Client Uploads File:**
    - A client uploads a file to the primary server.
    - The server calculates the file's hash and saves it.

2. **Replication Triggered:**
    - Server spawns replication threads for each cluster node in `CLUSTER_NODES`.
    - Each thread executes `_replicate_to_peer`, connecting to the specified peer server.

3. **Peer File Reception:**
    - Peer server validates upload and streams the file from the primary server.
    - Success or failure is logged for each node.

### File Deletion Replication
1. **Client Deletes File:**
    - A client sends a delete request to the primary server.
    - The server deletes the file locally and broadcasts a `file_removed` message.

2. **Peer Deletion Triggered:**
    - Peers receive the `file_removed` message and delete the file from their storage.

### Monitoring and Replication
1. **Local Monitoring:**
    - Each peer monitors the primary server for `file_added` and `file_removed` notifications.
    - Upon notification, appropriate replication actions (add/delete) are triggered for consistency.


## Error Handling
1. **Replication Failure:**
    - If a replication attempt to a peer fails, an error message is logged in the primary server's console.
    - Connection errors, upload rejections, or incomplete transfers prompt retries or specific debug follow-ups.

2. **Integrity Checks:**
    - Hash mismatches during uploads will reject the file and notify the client of the issue.

## Configuration Details
- **Cluster Nodes:** Defined in `main2.py` under `CLUSTER_NODES`.
- **Storage Paths:** Unique to each server replica; set in `server-replica.sh`.
- **Server Communication:** Uses TCP sockets with JSON-encoded control messages.


## Best Practices
- Ensure all peers are reachable to prevent data inconsistency.
- Periodically monitor logs for errors related to file transfers or deletions.
- Use the replica script to simplify the setup of a consistent testing environment.

---
End of Documentation.

