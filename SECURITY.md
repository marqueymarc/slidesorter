# Security policy

## Supported version

Security fixes target the latest release.

## Report a vulnerability

Use GitHub private vulnerability reporting when available. Do not open a public issue containing exploit details, private paths, or media.

Include:

- affected version;
- operating system;
- deployment method;
- reproduction steps using synthetic media;
- expected and actual path boundaries;
- whether any file moved or became exposed.

## Deployment boundary

SlideSorter is a trusted-user local application. It has write-capable filesystem APIs and no built-in authentication.

Safe defaults:

- bind to `127.0.0.1`;
- run one server per state directory;
- grant access only to trusted users;
- use Tailscale Serve for remote access;
- keep Stage and Remove paths deliberate;
- never run as root;
- never mount more filesystem scope than needed.

Do not expose SlideSorter directly to the public internet.

## Filesystem protections

The server validates relative IDs, decoded paths, configured roots, action destinations, and Undo roots. It refuses destination overwrite.

These checks reduce mistakes and traversal attacks. They do not protect against a malicious local administrator or compromised host.

## Privacy

Catalogs, configuration, thumbnails, and history reveal private filesystem information. Keep runtime state out of repositories, shared folders, and public backups.
