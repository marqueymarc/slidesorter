# Private remote access

## Threat model

SlideSorter exposes write-capable Stage, Remove, Settings, and Undo APIs. It has no built-in accounts, sessions, or passwords.

Never forward its port directly from an internet router. Never publish it through an anonymous tunnel.

## Tailscale Serve

Start SlideSorter on localhost:

```sh
slidesorter run "/path/to/Media"
```

In another terminal, publish it only to your tailnet:

```sh
tailscale serve --bg 8765
```

Open the private HTTPS URL printed by Tailscale.

Inspect exposure:

```sh
tailscale serve status
```

Disable exposure:

```sh
tailscale serve --https=443 off
```

## Operational requirements

Remote access requires:

- the media disk to remain mounted;
- SlideSorter to remain running;
- the host computer to remain awake;
- Tailscale to remain connected;
- the client to belong to the same authorized tailnet.

## Read-only access

SlideSorter does not currently provide a read-only role. If another person should only browse, do not give them access to the live server. Export a separate static contact sheet or use a purpose-built sharing service.

## Containers

Publishing a container port on `127.0.0.1` keeps it local:

```sh
docker run --rm -p 127.0.0.1:8765:8765 ...
```

Avoid `-p 8765:8765` on untrusted networks because that usually binds every host interface.
