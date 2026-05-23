# LLD: Zoom Video Call System

---

## 1. Requirements

### Functional
- Create/join/leave meetings
- Video/audio streaming (real-time, peer-to-peer or via server relay)
- Screen sharing
- Chat (in-meeting text messages)
- Participant management (mute, remove, host controls)
- Recording (meeting to cloud storage)
- Waiting room (host admits participants)
- Breakout rooms
- Raise hand / reactions

### Non-Functional
- < 150ms end-to-end latency (audio)
- Support 1000 participants in one meeting (webinar)
- 99.99% availability
- Automatic quality adaptation (network fluctuations)

---

## 2. Core Domain Models

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import uuid

class MeetingStatus(Enum):
    SCHEDULED = "scheduled"
    WAITING   = "waiting_room"
    ACTIVE    = "active"
    ENDED     = "ended"

class ParticipantRole(Enum):
    HOST         = "host"
    CO_HOST      = "co_host"
    PARTICIPANT  = "participant"
    PRESENTER    = "presenter"

class ParticipantState(Enum):
    IN_WAITING_ROOM = "waiting"
    ADMITTED        = "admitted"
    LEFT            = "left"
    REMOVED         = "removed"

class MediaState(Enum):
    OFF  = "off"
    ON   = "on"
    MUTED_BY_HOST = "muted_by_host"

@dataclass
class Participant:
    participant_id: str
    user_id:        str
    display_name:   str
    meeting_id:     str
    role:           ParticipantRole = ParticipantRole.PARTICIPANT
    state:          ParticipantState = ParticipantState.IN_WAITING_ROOM
    audio_state:    MediaState = MediaState.ON
    video_state:    MediaState = MediaState.ON
    is_screen_sharing: bool = False
    is_hand_raised: bool = False
    joined_at:      Optional[float] = None
    left_at:        Optional[float] = None
    connection_quality: int = 100    # 0-100, poor to excellent

    def is_host(self) -> bool:
        return self.role in (ParticipantRole.HOST, ParticipantRole.CO_HOST)

    def can_share_screen(self) -> bool:
        return (self.state == ParticipantState.ADMITTED and
                self.role != ParticipantRole.PARTICIPANT or
                self.role in (ParticipantRole.HOST, ParticipantRole.CO_HOST))


@dataclass
class Meeting:
    meeting_id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    host_id:      str = ""
    title:        str = ""
    passcode:     Optional[str] = None
    status:       MeetingStatus = MeetingStatus.SCHEDULED
    waiting_room_enabled: bool = True
    participants: dict[str, Participant] = field(default_factory=dict)
    chat_messages: list[dict] = field(default_factory=list)
    recording_active: bool = False
    screen_sharing_participant: Optional[str] = None   # participant_id
    scheduled_at: Optional[float] = None
    started_at:   Optional[float] = None
    ended_at:     Optional[float] = None
    max_participants: int = 100
    settings:     dict = field(default_factory=lambda: {
        "mute_on_entry": True,
        "allow_participant_rename": True,
        "allow_chat": True,
        "allow_reactions": True,
        "allow_screen_share": False   # only host by default
    })

    @property
    def active_participants(self) -> list[Participant]:
        return [p for p in self.participants.values()
                if p.state == ParticipantState.ADMITTED]

    @property
    def waiting_participants(self) -> list[Participant]:
        return [p for p in self.participants.values()
                if p.state == ParticipantState.IN_WAITING_ROOM]

    @property
    def participant_count(self) -> int:
        return len(self.active_participants)

    def get_host(self) -> Optional[Participant]:
        return next((p for p in self.participants.values()
                     if p.role == ParticipantRole.HOST), None)
```

---

## 3. Meeting Service

```python
class MeetingService:
    """Manages meeting lifecycle and participant operations."""

    def __init__(self, meeting_store, signaling_service, notification_service):
        self.store    = meeting_store
        self.signal   = signaling_service
        self.notifier = notification_service

    async def create_meeting(self, host_id: str, title: str,
                              passcode: str = None,
                              settings: dict = None) -> Meeting:
        """Create a new meeting."""
        meeting = Meeting(
            host_id=host_id,
            title=title,
            passcode=passcode,
            settings=settings or {}
        )

        # Create host participant
        host = Participant(
            participant_id=str(uuid.uuid4()),
            user_id=host_id,
            display_name=await self._get_display_name(host_id),
            meeting_id=meeting.meeting_id,
            role=ParticipantRole.HOST,
            state=ParticipantState.ADMITTED   # host always admitted
        )
        meeting.participants[host.participant_id] = host

        await self.store.save(meeting)
        return meeting

    async def join_meeting(self, meeting_id: str, user_id: str,
                            display_name: str,
                            passcode: str = None) -> dict:
        """Join a meeting. Returns join result with connection details."""
        meeting = await self.store.get(meeting_id)
        if not meeting:
            return {"error": "Meeting not found"}

        if meeting.status == MeetingStatus.ENDED:
            return {"error": "Meeting has ended"}

        # Verify passcode
        if meeting.passcode and meeting.passcode != passcode:
            return {"error": "Incorrect passcode"}

        # Check capacity
        if meeting.participant_count >= meeting.max_participants:
            return {"error": "Meeting is at capacity"}

        # Create participant
        participant = Participant(
            participant_id=str(uuid.uuid4()),
            user_id=user_id,
            display_name=display_name,
            meeting_id=meeting_id,
            audio_state=(MediaState.MUTED_BY_HOST
                         if meeting.settings.get("mute_on_entry") else MediaState.ON)
        )

        # Waiting room logic
        if meeting.waiting_room_enabled:
            participant.state = ParticipantState.IN_WAITING_ROOM
            meeting.participants[participant.participant_id] = participant
            await self.store.save(meeting)

            # Notify host about waiting participant
            await self.notifier.notify_host(meeting_id, {
                "type": "participant_waiting",
                "participant_id": participant.participant_id,
                "display_name": display_name
            })

            return {
                "status": "waiting",
                "participant_id": participant.participant_id,
                "message": "Waiting for host to admit you"
            }
        else:
            participant.state = ParticipantState.ADMITTED
            participant.joined_at = time.time()
            meeting.participants[participant.participant_id] = participant

            if meeting.status == MeetingStatus.SCHEDULED:
                meeting.status = MeetingStatus.ACTIVE
                meeting.started_at = time.time()

            await self.store.save(meeting)

            # Get media server connection details
            media_info = await self.signal.get_connection_info(
                meeting_id, participant.participant_id
            )

            # Notify others of new participant
            await self.signal.broadcast(meeting_id, {
                "type": "participant_joined",
                "participant_id": participant.participant_id,
                "display_name": display_name
            }, exclude=participant.participant_id)

            return {
                "status": "admitted",
                "participant_id": participant.participant_id,
                "media_server":   media_info,
                "participants":   [self._serialize_participant(p)
                                   for p in meeting.active_participants]
            }

    async def admit_from_waiting_room(self, meeting_id: str,
                                       host_participant_id: str,
                                       participant_id: str) -> bool:
        """Host admits a waiting participant."""
        meeting = await self.store.get(meeting_id)
        host = meeting.participants.get(host_participant_id)

        if not host or not host.is_host():
            return False

        participant = meeting.participants.get(participant_id)
        if not participant or participant.state != ParticipantState.IN_WAITING_ROOM:
            return False

        participant.state = ParticipantState.ADMITTED
        participant.joined_at = time.time()
        await self.store.save(meeting)

        # Notify the waiting participant they've been admitted
        media_info = await self.signal.get_connection_info(
            meeting_id, participant_id
        )
        await self.signal.send_to_participant(participant_id, {
            "type": "admitted",
            "media_server": media_info
        })

        # Notify all active participants
        await self.signal.broadcast(meeting_id, {
            "type": "participant_joined",
            "participant_id": participant_id,
            "display_name": participant.display_name
        })
        return True

    async def leave_meeting(self, meeting_id: str,
                             participant_id: str) -> bool:
        """Participant leaves the meeting."""
        meeting = await self.store.get(meeting_id)
        participant = meeting.participants.get(participant_id)
        if not participant:
            return False

        participant.state = ParticipantState.LEFT
        participant.left_at = time.time()

        # If host leaves, transfer host or end meeting
        if participant.role == ParticipantRole.HOST:
            co_hosts = [p for p in meeting.active_participants
                        if p.role == ParticipantRole.CO_HOST]
            if co_hosts:
                await self.transfer_host(meeting_id, co_hosts[0].participant_id)
            elif meeting.active_participants:
                # Promote oldest participant to host
                next_host = min(meeting.active_participants,
                                key=lambda p: p.joined_at or float("inf"))
                await self.transfer_host(meeting_id, next_host.participant_id)
            else:
                await self.end_meeting(meeting_id, participant_id)

        await self.store.save(meeting)
        await self.signal.broadcast(meeting_id, {
            "type": "participant_left",
            "participant_id": participant_id
        })
        return True

    async def end_meeting(self, meeting_id: str,
                           host_participant_id: str) -> bool:
        """Host ends the meeting for all."""
        meeting = await self.store.get(meeting_id)
        host = meeting.participants.get(host_participant_id)

        if not host or not host.is_host():
            return False

        meeting.status = MeetingStatus.ENDED
        meeting.ended_at = time.time()

        for p in meeting.participants.values():
            if p.state == ParticipantState.ADMITTED:
                p.state = ParticipantState.LEFT
                p.left_at = time.time()

        await self.store.save(meeting)

        # Notify all participants to disconnect
        await self.signal.broadcast(meeting_id, {"type": "meeting_ended"})
        return True

    def _serialize_participant(self, p: Participant) -> dict:
        return {
            "participant_id":    p.participant_id,
            "display_name":      p.display_name,
            "role":              p.role.value,
            "audio_state":       p.audio_state.value,
            "video_state":       p.video_state.value,
            "is_screen_sharing": p.is_screen_sharing,
            "is_hand_raised":    p.is_hand_raised
        }

    async def _get_display_name(self, user_id: str) -> str:
        # Fetch from user service
        return f"User-{user_id[:8]}"

    async def transfer_host(self, meeting_id: str,
                             new_host_participant_id: str):
        meeting = await self.store.get(meeting_id)
        old_host = meeting.get_host()
        if old_host:
            old_host.role = ParticipantRole.PARTICIPANT
        new_host = meeting.participants.get(new_host_participant_id)
        if new_host:
            new_host.role = ParticipantRole.HOST
        await self.store.save(meeting)
        await self.signal.broadcast(meeting_id, {
            "type": "host_changed",
            "new_host_participant_id": new_host_participant_id
        })
```

---

## 4. Host Controls

```python
class HostControlService:
    """Actions only the host/co-host can perform."""

    def __init__(self, meeting_service: MeetingService,
                  meeting_store, signaling_service):
        self.meeting_svc = meeting_service
        self.store       = meeting_store
        self.signal      = signaling_service

    async def _verify_host(self, meeting_id: str,
                            host_pid: str) -> tuple[bool, "Meeting"]:
        meeting = await self.store.get(meeting_id)
        host = meeting.participants.get(host_pid)
        return bool(host and host.is_host()), meeting

    async def mute_participant(self, meeting_id: str, host_pid: str,
                                target_pid: str) -> bool:
        ok, meeting = await self._verify_host(meeting_id, host_pid)
        if not ok: return False

        target = meeting.participants.get(target_pid)
        if not target: return False

        target.audio_state = MediaState.MUTED_BY_HOST
        await self.store.save(meeting)
        await self.signal.send_to_participant(target_pid, {
            "type": "muted_by_host"
        })
        return True

    async def mute_all(self, meeting_id: str, host_pid: str) -> bool:
        ok, meeting = await self._verify_host(meeting_id, host_pid)
        if not ok: return False

        host = meeting.participants.get(host_pid)
        for p in meeting.active_participants:
            if p.participant_id != host.participant_id:
                p.audio_state = MediaState.MUTED_BY_HOST
                await self.signal.send_to_participant(p.participant_id, {
                    "type": "muted_by_host"
                })
        await self.store.save(meeting)
        return True

    async def remove_participant(self, meeting_id: str, host_pid: str,
                                  target_pid: str) -> bool:
        ok, meeting = await self._verify_host(meeting_id, host_pid)
        if not ok: return False

        target = meeting.participants.get(target_pid)
        if not target or target.role == ParticipantRole.HOST:
            return False

        target.state = ParticipantState.REMOVED
        target.left_at = time.time()
        await self.store.save(meeting)

        await self.signal.send_to_participant(target_pid, {
            "type": "removed_from_meeting"
        })
        await self.signal.broadcast(meeting_id, {
            "type": "participant_removed",
            "participant_id": target_pid
        }, exclude=target_pid)
        return True

    async def promote_to_co_host(self, meeting_id: str, host_pid: str,
                                  target_pid: str) -> bool:
        ok, meeting = await self._verify_host(meeting_id, host_pid)
        if not ok: return False

        target = meeting.participants.get(target_pid)
        if not target: return False

        target.role = ParticipantRole.CO_HOST
        await self.store.save(meeting)
        await self.signal.broadcast(meeting_id, {
            "type": "role_changed",
            "participant_id": target_pid,
            "new_role": "co_host"
        })
        return True

    async def allow_screen_share(self, meeting_id: str, host_pid: str,
                                  allow: bool) -> bool:
        ok, meeting = await self._verify_host(meeting_id, host_pid)
        if not ok: return False

        meeting.settings["allow_screen_share"] = allow
        await self.store.save(meeting)
        await self.signal.broadcast(meeting_id, {
            "type": "settings_changed",
            "allow_screen_share": allow
        })
        return True

    async def lock_meeting(self, meeting_id: str, host_pid: str) -> bool:
        ok, meeting = await self._verify_host(meeting_id, host_pid)
        if not ok: return False

        meeting.settings["locked"] = True
        await self.store.save(meeting)
        return True
```

---

## 5. WebRTC Signaling

```python
"""
WebRTC: peer-to-peer media (for small meetings, 2-4 people).
SFU (Selective Forwarding Unit): for large meetings.
  - Each participant sends 1 stream to media server
  - Media server selects and forwards relevant streams to each client
  - Reduces bandwidth: N streams sent total instead of N×(N-1)

Signaling: exchange of SDP (Session Description Protocol) offers/answers
  and ICE candidates through your server.
"""

import asyncio
import json
from collections import defaultdict

class SignalingService:
    """
    WebSocket-based signaling for WebRTC negotiation.
    Handles offer/answer exchange and ICE candidates.
    """

    def __init__(self):
        # participant_id → WebSocket connection
        self._connections: dict[str, object] = {}
        # meeting_id → set of participant_ids
        self._meeting_participants: dict[str, set] = defaultdict(set)

    async def register(self, participant_id: str, meeting_id: str,
                        websocket):
        """Register WebSocket connection for a participant."""
        self._connections[participant_id] = websocket
        self._meeting_participants[meeting_id].add(participant_id)
        await self._send(participant_id, {"type": "registered",
                                           "participant_id": participant_id})

    async def unregister(self, participant_id: str, meeting_id: str):
        """Remove WebSocket connection."""
        self._connections.pop(participant_id, None)
        self._meeting_participants[meeting_id].discard(participant_id)

    async def handle_signal(self, participant_id: str, message: dict):
        """
        Route WebRTC signaling messages between peers.
        Message types: offer, answer, ice_candidate
        """
        msg_type = message.get("type")
        target_id = message.get("target_participant_id")

        if msg_type in ("offer", "answer", "ice_candidate"):
            if target_id:
                # P2P signaling: forward to specific peer
                await self._send(target_id, {
                    **message,
                    "from_participant_id": participant_id
                })
            else:
                # SFU signaling: message is for media server
                await self._send_to_media_server(participant_id, message)

        elif msg_type == "raise_hand":
            meeting_id = message.get("meeting_id")
            await self.broadcast(meeting_id, {
                "type": "hand_raised",
                "participant_id": participant_id
            })

        elif msg_type == "reaction":
            meeting_id = message.get("meeting_id")
            await self.broadcast(meeting_id, {
                "type": "reaction",
                "participant_id": participant_id,
                "reaction": message.get("reaction")   # 👍❤️😂👏
            })

        elif msg_type == "chat":
            meeting_id = message.get("meeting_id")
            await self.broadcast(meeting_id, {
                "type": "chat_message",
                "from_participant_id": participant_id,
                "message": message.get("message"),
                "timestamp": time.time()
            })

    async def broadcast(self, meeting_id: str, message: dict,
                         exclude: str = None):
        """Send message to all participants in a meeting."""
        participant_ids = self._meeting_participants.get(meeting_id, set())
        tasks = []
        for pid in participant_ids:
            if pid != exclude:
                tasks.append(self._send(pid, message))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send_to_participant(self, participant_id: str, message: dict):
        await self._send(participant_id, message)

    async def _send(self, participant_id: str, message: dict):
        ws = self._connections.get(participant_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                self._connections.pop(participant_id, None)

    async def get_connection_info(self, meeting_id: str,
                                   participant_id: str) -> dict:
        """Return SFU/TURN server connection details for this participant."""
        return {
            "sfu_server":    "wss://sfu-us-east.zoom.us/ws",
            "turn_servers": [
                {
                    "urls":       "turn:turn-us.zoom.us:3478",
                    "username":   participant_id,
                    "credential": self._generate_turn_credential(participant_id)
                }
            ],
            "room_token":    self._generate_room_token(meeting_id, participant_id)
        }

    def _generate_turn_credential(self, participant_id: str) -> str:
        import hmac
        import hashlib
        import base64
        return base64.b64encode(
            hmac.new(b"secret", participant_id.encode(), hashlib.sha1).digest()
        ).decode()

    def _generate_room_token(self, meeting_id: str, participant_id: str) -> str:
        return f"token_{meeting_id}_{participant_id}"

    async def _send_to_media_server(self, participant_id: str, message: dict):
        """Forward SDP to SFU media server."""
        pass   # SFU handles internally


class ChatService:
    """In-meeting chat with persistence."""

    async def send_message(self, meeting_id: str, sender_pid: str,
                            content: str, to_pid: str = None) -> dict:
        """
        Send chat message.
        to_pid=None: broadcast to all (public).
        to_pid set: private message.
        """
        msg = {
            "message_id":   str(uuid.uuid4()),
            "meeting_id":   meeting_id,
            "sender_pid":   sender_pid,
            "content":      content,
            "to_pid":       to_pid,   # None = public
            "timestamp":    time.time()
        }
        await self.store.save_message(msg)
        return msg

    async def get_messages(self, meeting_id: str,
                            after_ts: float = 0) -> list[dict]:
        return await self.store.get_messages(meeting_id, after_ts)
```

---

## 6. Recording Service

```python
class RecordingService:
    """
    Cloud recording: capture meeting audio/video to S3.
    Strategy: server-side recording via SFU composite streams.
    """

    async def start_recording(self, meeting_id: str,
                               host_pid: str) -> dict:
        """Start cloud recording for a meeting."""
        # Request SFU to start recording composite stream
        recording_id = str(uuid.uuid4())
        s3_path = f"recordings/{meeting_id}/{recording_id}.mp4"

        await self.sfu_client.start_recording(meeting_id, {
            "recording_id": recording_id,
            "output_path":  s3_path,
            "format":       "mp4",
            "layout":       "gallery"   # grid of participants
        })

        await self.store.create_recording({
            "recording_id": recording_id,
            "meeting_id":   meeting_id,
            "started_by":   host_pid,
            "started_at":   time.time(),
            "status":       "recording",
            "s3_path":      s3_path
        })

        return {"recording_id": recording_id, "status": "recording"}

    async def stop_recording(self, meeting_id: str,
                              recording_id: str) -> dict:
        """Stop recording and finalize S3 upload."""
        await self.sfu_client.stop_recording(meeting_id, recording_id)

        # Update record
        await self.store.update_recording(recording_id, {
            "status":   "processing",
            "ended_at": time.time()
        })

        # Async processing job: transcode + generate thumbnail
        await self.kafka.send("recording_jobs", {
            "recording_id": recording_id,
            "meeting_id":   meeting_id
        })
        return {"recording_id": recording_id, "status": "processing"}

    async def get_recording_url(self, recording_id: str,
                                 user_id: str) -> str:
        """Generate time-limited presigned URL for recording download."""
        recording = await self.store.get_recording(recording_id)
        # Verify user has access (was in meeting)
        if not await self._can_access(user_id, recording["meeting_id"]):
            raise PermissionError("Access denied")

        # Presigned S3 URL (valid 1 hour)
        return await self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": "zoom-recordings", "Key": recording["s3_path"]},
            ExpiresIn=3600
        )

    async def _can_access(self, user_id: str, meeting_id: str) -> bool:
        # Check if user was a participant
        return await self.store.was_participant(user_id, meeting_id)
```

---

## 7. Breakout Rooms

```python
class BreakoutRoomService:
    """Split meeting participants into smaller sub-rooms."""

    async def create_breakout_rooms(self, meeting_id: str,
                                     host_pid: str,
                                     num_rooms: int,
                                     assignments: dict[str, int] = None) -> list[dict]:
        """
        Create N breakout rooms.
        assignments: {participant_id → room_number} (optional)
        If no assignments: auto-assign evenly.
        """
        meeting = await self.meeting_store.get(meeting_id)
        host = meeting.participants.get(host_pid)
        if not host or not host.is_host():
            raise PermissionError("Only host can create breakout rooms")

        rooms = []
        for i in range(num_rooms):
            room = {
                "room_id":     str(uuid.uuid4()),
                "meeting_id":  meeting_id,
                "room_number": i + 1,
                "name":        f"Breakout Room {i + 1}",
                "participants": []
            }
            rooms.append(room)

        # Auto-assign if no assignments provided
        if not assignments:
            active = meeting.active_participants
            for idx, p in enumerate(active):
                if p.participant_id == host_pid:
                    continue
                room_num = idx % num_rooms
                rooms[room_num]["participants"].append(p.participant_id)
        else:
            for pid, room_num in assignments.items():
                if 0 <= room_num < num_rooms:
                    rooms[room_num]["participants"].append(pid)

        await self.store.save_breakout_rooms(meeting_id, rooms)

        # Notify each participant of their room assignment
        for room in rooms:
            for pid in room["participants"]:
                await self.signaling.send_to_participant(pid, {
                    "type":    "breakout_room_assigned",
                    "room_id": room["room_id"],
                    "room_name": room["name"]
                })

        return rooms

    async def end_breakout_rooms(self, meeting_id: str,
                                  host_pid: str) -> bool:
        """Bring all participants back to main meeting."""
        meeting = await self.meeting_store.get(meeting_id)
        host = meeting.participants.get(host_pid)
        if not host or not host.is_host():
            return False

        await self.signaling.broadcast(meeting_id, {
            "type": "breakout_rooms_ended",
            "message": "Please return to the main meeting"
        })
        await self.store.clear_breakout_rooms(meeting_id)
        return True
```

---

## 8. System Architecture

```
Client (Web/Desktop/Mobile)
    │ WebSocket (signaling)
    │ WebRTC (media via SFU)
    ▼
API Gateway
    │
    ├── Meeting Service (REST API)
    │       └── Meeting Store (Redis + PostgreSQL)
    │
    ├── Signaling Service (WebSocket)
    │       └── Redis Pub/Sub (multi-server WebSocket broadcast)
    │
    └── SFU Media Server (Mediasoup / Janus)
            └── Media streams (RTP/SRTP)
                    │
                    └── Recording Service → S3
```

---

## 9. Interview Questions

**Q1: How does WebRTC work and what is a SFU?**
> WebRTC: browser-native P2P media (audio/video) using UDP. P2P works for 2-4 people. For larger groups: SFU (Selective Forwarding Unit) — each participant sends 1 stream to the SFU server; SFU selects and forwards relevant streams to each client. Without SFU: N participants × N-1 streams each = N² bandwidth. With SFU: N streams total. SFU also enables recording (server-side composite).

**Q2: What is signaling in WebRTC and why does it need your server?**
> WebRTC handles media but not how peers find each other. Signaling = exchange of SDP (what codecs, IPs, ports) and ICE candidates (NAT traversal) between peers. Browser can't find another browser directly — your server acts as the relay (signaling server via WebSocket). Once peers exchange SDP, direct media flows peer-to-peer. TURN server needed when P2P fails (symmetric NAT): relays media bytes through server.

**Q3: How would you scale the signaling service to millions of meetings?**
> Stateless signaling servers + Redis Pub/Sub for cross-server WebSocket broadcast. Client connects to any server. Server subscribes to meeting channel in Redis. `broadcast(meeting_id, msg)` → publish to Redis → all servers subscribed to that meeting forward to their local WebSocket connections. Meeting-server affinity via consistent hashing (same meeting → same server group) reduces Redis overhead.

**Q4: How does the waiting room work technically?**
> Participant's WebSocket connects but they don't get media server credentials until admitted. State stored as `IN_WAITING_ROOM` in DB/Redis. Signaling service notifies host of waiting participants. When host admits: update state to `ADMITTED`, send media server JWT/token to participant's WebSocket. Participant uses token to join SFU room. Host sees waiting list in real-time via WebSocket push.

**Q5: How do you implement mute-all without polling?**
> Server sends a WebRTC data channel message or signaling message to each participant: `{"type": "muted_by_host"}`. Client receives and disables microphone (stops audio track). Server updates state in DB. Client can send signal requesting unmute — host has setting to allow/deny self-unmute. Server-side muting (not trusting client): SFU can drop audio RTP packets from muted participant.

**Q6: How would you handle poor network quality in a video call?**
> (1) ABR (Adaptive Bitrate): SFU sends lower resolution/frame rate to participants with poor connections based on RTCP feedback. (2) SimulCast: each participant sends 3 stream qualities (360p/720p/1080p); SFU forwards appropriate quality per receiver. (3) SVC (Scalable Video Coding): single stream with quality layers. (4) Connection quality signals from RTCP NACK (packet loss), REMB (bandwidth estimation). (5) Auto-disable video at poor quality.
