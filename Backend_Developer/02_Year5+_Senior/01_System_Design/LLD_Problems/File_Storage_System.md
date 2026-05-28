# File Storage System (Google Drive/Dropbox) LLD

## Quick Reference Card
```
Pattern Used    → Composite (folder tree), Strategy (storage backend), Observer (sync events)
Core Challenge  → Hierarchy (nested folders), Permissions, Versioning, Deduplication
Key Classes     → File, Folder, FileNode (Composite), Permission, StorageService
Key Insight     → "Content-addressable storage: same bytes = same hash = stored ONCE"
Interview Hook  → "Composite pattern for file/folder tree + content hash deduplication"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Google Drive type system mein:
- **File** — actual content (bytes)
- **Folder** — container of files + folders (recursive)
- **Permission** — kaun dekh sakta hai, edit kar sakta hai
- **Version** — file ka history (har save = new version)

**Composite Pattern:** File aur Folder dono `FileNode` hain. Folder ke andar files aur aur folders ho sakte hain (recursive). Isko "Composite Pattern" kehte hain — leaf (File) aur container (Folder) ka same interface.

**Content Addressing (Deduplication):**
```
File A: "Hello World" → SHA256 = abc123
File B: "Hello World" → SHA256 = abc123 (same!)

Storage mein sirf ek copy hoga.
Dono files same hash pe point karenge.
Ek 1TB file jo 1000 users share karein → storage mein sirf ek copy = 1TB (not 1000TB)
```

### 1.2 Code

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from datetime import datetime
import hashlib
import uuid
import threading
import io

# ===== ENUMS =====

class NodeType(Enum):
    FILE = "FILE"
    FOLDER = "FOLDER"

class PermissionLevel(Enum):
    VIEWER = "VIEWER"       # Read only
    COMMENTER = "COMMENTER" # Read + comment
    EDITOR = "EDITOR"       # Read + write
    OWNER = "OWNER"         # Full control + share

class SharingScope(Enum):
    PRIVATE = "PRIVATE"             # Only owner
    SPECIFIC_USERS = "SPECIFIC_USERS"
    ANYONE_WITH_LINK = "ANYONE_WITH_LINK"
    PUBLIC = "PUBLIC"               # Anyone can view

class VersionStatus(Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

# ===== PERMISSION =====

@dataclass
class Permission:
    """Ek user ko kitna access hai ek file/folder pe"""
    user_id: str
    level: PermissionLevel
    granted_by: str
    granted_at: datetime = field(default_factory=datetime.now)
    can_share: bool = False       # Kya yeh user aur logo ko share kar sakta hai?
    expiry: Optional[datetime] = None

# ===== VERSION =====

@dataclass
class FileVersion:
    """
    File ka ek version — har save pe naya version
    Content hash se actual bytes fetch hote hain storage se
    """
    version_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    version_number: int = 1
    content_hash: str = ""        # SHA256 — storage mein dhundne ki key
    size_bytes: int = 0
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    change_summary: str = ""
    status: VersionStatus = VersionStatus.ACTIVE

# ===== COMPOSITE PATTERN: FileNode =====

class FileNode:
    """
    Abstract base — File aur Folder dono isko inherit karte hain
    Composite Pattern: uniform interface for single file and file tree
    """
    
    def __init__(self, name: str, owner_id: str):
        self.node_id: str = str(uuid.uuid4())
        self.name: str = name
        self.owner_id: str = owner_id
        self.parent_id: Optional[str] = None
        self.created_at: datetime = datetime.now()
        self.modified_at: datetime = datetime.now()
        self.sharing_scope: SharingScope = SharingScope.PRIVATE
        self._permissions: Dict[str, Permission] = {}   # user_id → Permission
        self._lock = threading.Lock()
    
    @property
    def node_type(self) -> NodeType:
        raise NotImplementedError
    
    def get_size(self) -> int:
        """File = actual bytes, Folder = sum of children"""
        raise NotImplementedError
    
    def get_path(self, storage: 'StorageService') -> str:
        """Root se current node tak ka path"""
        raise NotImplementedError
    
    # ---- Permission Management ----
    
    def grant_permission(self, user_id: str, level: PermissionLevel,
                         granted_by: str, can_share: bool = False):
        with self._lock:
            self._permissions[user_id] = Permission(
                user_id=user_id, level=level,
                granted_by=granted_by, can_share=can_share
            )
    
    def revoke_permission(self, user_id: str):
        with self._lock:
            self._permissions.pop(user_id, None)
    
    def get_permission(self, user_id: str) -> Optional[PermissionLevel]:
        """User ka permission level kya hai?"""
        if user_id == self.owner_id:
            return PermissionLevel.OWNER
        
        perm = self._permissions.get(user_id)
        if not perm:
            return None
        
        # Check expiry
        if perm.expiry and datetime.now() > perm.expiry:
            self._permissions.pop(user_id, None)
            return None
        
        return perm.level
    
    def can_read(self, user_id: str) -> bool:
        if self.sharing_scope in [SharingScope.ANYONE_WITH_LINK, SharingScope.PUBLIC]:
            return True
        level = self.get_permission(user_id)
        return level is not None  # Any permission = can read
    
    def can_write(self, user_id: str) -> bool:
        level = self.get_permission(user_id)
        return level in [PermissionLevel.EDITOR, PermissionLevel.OWNER]
    
    def can_share(self, user_id: str) -> bool:
        if user_id == self.owner_id:
            return True
        perm = self._permissions.get(user_id)
        return perm is not None and perm.can_share

# ===== FILE (Leaf Node) =====

class File(FileNode):
    """
    Actual file — content in storage backend
    Versions ka list maintain karta hai
    """
    
    def __init__(self, name: str, owner_id: str, mime_type: str = "application/octet-stream"):
        super().__init__(name, owner_id)
        self.mime_type = mime_type
        self.extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        self._versions: List[FileVersion] = []
        self.current_version: Optional[FileVersion] = None
    
    @property
    def node_type(self) -> NodeType:
        return NodeType.FILE
    
    def get_size(self) -> int:
        return self.current_version.size_bytes if self.current_version else 0
    
    def add_version(self, content_hash: str, size_bytes: int,
                    uploaded_by: str, change_summary: str = "") -> FileVersion:
        """New version add karo"""
        version_num = len(self._versions) + 1
        version = FileVersion(
            version_number=version_num,
            content_hash=content_hash,
            size_bytes=size_bytes,
            created_by=uploaded_by,
            change_summary=change_summary
        )
        self._versions.append(version)
        self.current_version = version
        self.modified_at = datetime.now()
        return version
    
    def get_version(self, version_id: str) -> Optional[FileVersion]:
        return next((v for v in self._versions if v.version_id == version_id), None)
    
    def get_version_history(self) -> List[FileVersion]:
        return sorted(self._versions, key=lambda v: v.version_number, reverse=True)
    
    def restore_version(self, version_id: str, restored_by: str) -> FileVersion:
        """Purana version restore karo"""
        old_version = self.get_version(version_id)
        if not old_version:
            raise ValueError(f"Version {version_id} not found")
        
        # Restore = new version pointing to old content hash
        return self.add_version(
            content_hash=old_version.content_hash,
            size_bytes=old_version.size_bytes,
            uploaded_by=restored_by,
            change_summary=f"Restored from v{old_version.version_number}"
        )

# ===== FOLDER (Composite Node) =====

class Folder(FileNode):
    """
    Container — files aur subfolders rakh sakta hai
    Recursive size calculation = sum of all children
    """
    
    def __init__(self, name: str, owner_id: str):
        super().__init__(name, owner_id)
        self._children: Dict[str, FileNode] = {}  # node_id → FileNode
        self._name_index: Dict[str, str] = {}      # name → node_id (for quick lookup)
    
    @property
    def node_type(self) -> NodeType:
        return NodeType.FOLDER
    
    def get_size(self) -> int:
        """Recursive size — all children"""
        return sum(child.get_size() for child in self._children.values())
    
    def add_child(self, node: FileNode):
        """Child add karo — name conflict check"""
        if node.name in self._name_index:
            raise ValueError(f"'{node.name}' already exists in this folder")
        self._children[node.node_id] = node
        self._name_index[node.name] = node.node_id
        node.parent_id = self.node_id
    
    def remove_child(self, node_id: str):
        node = self._children.pop(node_id, None)
        if node:
            self._name_index.pop(node.name, None)
    
    def get_child_by_name(self, name: str) -> Optional[FileNode]:
        node_id = self._name_index.get(name)
        return self._children.get(node_id) if node_id else None
    
    def list_children(self) -> List[FileNode]:
        """Folders pehle, phir files, alphabetically"""
        children = list(self._children.values())
        folders = sorted([c for c in children if c.node_type == NodeType.FOLDER],
                         key=lambda x: x.name)
        files = sorted([c for c in children if c.node_type == NodeType.FILE],
                       key=lambda x: x.name)
        return folders + files
    
    def find_recursive(self, name: str) -> List[FileNode]:
        """Deep search — name se file/folder dhundo"""
        results = []
        for child in self._children.values():
            if name.lower() in child.name.lower():
                results.append(child)
            if isinstance(child, Folder):
                results.extend(child.find_recursive(name))
        return results

# ===== CONTENT STORE (Deduplication) =====

class ContentStore:
    """
    Content-addressable storage
    
    SHA256 hash = unique identifier for content
    Same content → same hash → stored ONCE
    
    Real: S3/GCS with object key = content hash
    Yahan: in-memory dict
    """
    
    def __init__(self):
        # content_hash → bytes
        self._storage: Dict[str, bytes] = {}
        # content_hash → reference count (how many files point to it)
        self._ref_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def store(self, content: bytes) -> tuple[str, int]:
        """
        Content store karo
        Returns: (content_hash, size_bytes)
        Agar already exists → reference count badhao, bytes store mat karo
        """
        content_hash = hashlib.sha256(content).hexdigest()
        size = len(content)
        
        with self._lock:
            if content_hash not in self._storage:
                self._storage[content_hash] = content
                self._ref_counts[content_hash] = 0
                print(f"  [Store] NEW content stored: {content_hash[:8]}... ({size} bytes)")
            else:
                print(f"  [Store] DEDUPLICATED: {content_hash[:8]}... already exists → ref++")
            
            self._ref_counts[content_hash] += 1
        
        return content_hash, size
    
    def retrieve(self, content_hash: str) -> Optional[bytes]:
        """Hash se content retrieve karo"""
        return self._storage.get(content_hash)
    
    def release(self, content_hash: str):
        """File delete hone pe reference count ghataao"""
        with self._lock:
            if content_hash in self._ref_counts:
                self._ref_counts[content_hash] -= 1
                if self._ref_counts[content_hash] == 0:
                    # Koi file point nahi kar rahi → garbage collect
                    del self._storage[content_hash]
                    del self._ref_counts[content_hash]
                    print(f"  [Store] Garbage collected: {content_hash[:8]}...")
    
    def get_total_unique_size(self) -> int:
        return sum(len(content) for content in self._storage.values())
    
    def get_dedup_ratio(self, total_logical_size: int) -> float:
        physical = self.get_total_unique_size()
        return total_logical_size / physical if physical > 0 else 1.0

# ===== STORAGE QUOTA =====

@dataclass
class StorageQuota:
    user_id: str
    total_bytes: int = 15 * 1024 * 1024 * 1024  # 15 GB (like Google Drive free)
    used_bytes: int = 0
    
    @property
    def available_bytes(self) -> int:
        return self.total_bytes - self.used_bytes
    
    @property
    def usage_percentage(self) -> float:
        return (self.used_bytes / self.total_bytes) * 100
    
    def can_upload(self, file_size: int) -> bool:
        return self.used_bytes + file_size <= self.total_bytes
    
    def human_readable_used(self) -> str:
        return self._format(self.used_bytes)
    
    def human_readable_total(self) -> str:
        return self._format(self.total_bytes)
    
    @staticmethod
    def _format(bytes_val: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} PB"

# ===== STORAGE SERVICE (Facade) =====

class StorageService:
    """
    Main facade — file storage ka pura system
    
    Business Rules:
    - User ka storage quota (15GB free)
    - Permission-based access
    - Automatic versioning on upload
    - Deduplication (same content = same hash)
    - Soft delete (trash → 30 days → permanent delete)
    """
    
    def __init__(self):
        # user_id → root Folder (each user has their own root)
        self._user_roots: Dict[str, Folder] = {}
        # node_id → FileNode (global index)
        self._nodes: Dict[str, FileNode] = {}
        # user_id → StorageQuota
        self._quotas: Dict[str, StorageQuota] = {}
        # Trash: node_id → (FileNode, deleted_at)
        self._trash: Dict[str, tuple] = {}
        
        self.content_store = ContentStore()
        self._lock = threading.RLock()
    
    # ---- User Setup ----
    
    def create_user_storage(self, user_id: str, quota_bytes: int = None) -> Folder:
        """New user ke liye root folder create karo"""
        root = Folder(name="My Drive", owner_id=user_id)
        self._user_roots[user_id] = root
        self._nodes[root.node_id] = root
        self._quotas[user_id] = StorageQuota(
            user_id=user_id,
            total_bytes=quota_bytes or 15 * 1024 * 1024 * 1024
        )
        print(f"[Drive] User storage created: {user_id} ({self._quotas[user_id].human_readable_total()})")
        return root
    
    def get_root(self, user_id: str) -> Folder:
        root = self._user_roots.get(user_id)
        if not root:
            raise ValueError(f"User {user_id} has no storage")
        return root
    
    # ---- Create Folder ----
    
    def create_folder(self, parent_id: str, name: str, owner_id: str) -> Folder:
        """Naya folder create karo"""
        parent = self._get_node(parent_id, Folder)
        
        if not parent.can_write(owner_id):
            raise PermissionError(f"No write permission in folder '{parent.name}'")
        
        folder = Folder(name=name, owner_id=owner_id)
        parent.add_child(folder)
        self._nodes[folder.node_id] = folder
        
        print(f"[Drive] Folder created: '{name}' in '{parent.name}'")
        return folder
    
    # ---- Upload File ----
    
    def upload_file(self, parent_id: str, name: str, content: bytes,
                    uploaded_by: str, mime_type: str = "application/octet-stream",
                    change_summary: str = "") -> File:
        """
        File upload karo
        
        Steps:
        1. Parent folder check
        2. Permission check
        3. Quota check
        4. Content store (deduplication)
        5. File node create/update
        6. Version add
        """
        with self._lock:
            parent = self._get_node(parent_id, Folder)
            
            if not parent.can_write(uploaded_by):
                raise PermissionError(f"No write permission")
            
            # Check if file already exists with same name
            existing = parent.get_child_by_name(name)
            
            if existing and isinstance(existing, File):
                # Update existing file (new version)
                return self._update_file(existing, content, uploaded_by, change_summary)
            elif existing:
                raise ValueError(f"'{name}' is a folder, not a file")
            
            # Quota check
            quota = self._quotas.get(uploaded_by)
            if quota and not quota.can_upload(len(content)):
                raise ValueError(
                    f"Storage full! Available: {quota.human_readable_used()}/{quota.human_readable_total()}"
                )
            
            # Store content
            content_hash, size = self.content_store.store(content)
            
            # Create file node
            file_node = File(name=name, owner_id=uploaded_by, mime_type=mime_type)
            file_node.add_version(content_hash, size, uploaded_by, change_summary)
            parent.add_child(file_node)
            self._nodes[file_node.node_id] = file_node
            
            # Update quota
            if quota:
                quota.used_bytes += size
            
            print(f"[Drive] Uploaded: '{name}' ({size} bytes) → '{parent.name}'")
            return file_node
    
    def _update_file(self, file_node: File, content: bytes,
                     updated_by: str, change_summary: str) -> File:
        """Existing file update karo (new version)"""
        if not file_node.can_write(updated_by):
            raise PermissionError("No write permission")
        
        content_hash, size = self.content_store.store(content)
        file_node.add_version(content_hash, size, updated_by, change_summary)
        
        # Quota update
        quota = self._quotas.get(file_node.owner_id)
        if quota:
            quota.used_bytes += size
        
        print(f"[Drive] Updated: '{file_node.name}' v{file_node.current_version.version_number}")
        return file_node
    
    # ---- Download File ----
    
    def download_file(self, node_id: str, requesting_user: str,
                      version_id: str = None) -> bytes:
        """File download karo"""
        file_node = self._get_node(node_id, File)
        
        if not file_node.can_read(requesting_user):
            raise PermissionError("No read permission")
        
        if version_id:
            version = file_node.get_version(version_id)
            if not version:
                raise ValueError(f"Version {version_id} not found")
        else:
            version = file_node.current_version
        
        if not version:
            raise ValueError("File has no content")
        
        content = self.content_store.retrieve(version.content_hash)
        if not content:
            raise ValueError("Content not found in storage")
        
        print(f"[Drive] Downloaded: '{file_node.name}' v{version.version_number} "
              f"({version.size_bytes} bytes)")
        return content
    
    # ---- Move / Copy ----
    
    def move_node(self, node_id: str, new_parent_id: str, moved_by: str):
        """File/folder move karo"""
        node = self._get_node(node_id)
        new_parent = self._get_node(new_parent_id, Folder)
        
        if not node.can_write(moved_by):
            raise PermissionError("No permission to move")
        if not new_parent.can_write(moved_by):
            raise PermissionError("No write permission in destination")
        
        # Old parent se remove karo
        if node.parent_id:
            old_parent = self._nodes.get(node.parent_id)
            if old_parent and isinstance(old_parent, Folder):
                old_parent.remove_child(node_id)
        
        new_parent.add_child(node)
        print(f"[Drive] Moved: '{node.name}' → '{new_parent.name}'")
    
    def copy_file(self, file_id: str, dest_folder_id: str,
                  copied_by: str, new_name: str = None) -> File:
        """File copy karo — content same hash use karo (deduplication!)"""
        original = self._get_node(file_id, File)
        dest_folder = self._get_node(dest_folder_id, Folder)
        
        if not original.can_read(copied_by):
            raise PermissionError("No read permission on source")
        if not dest_folder.can_write(copied_by):
            raise PermissionError("No write permission in destination")
        
        # Copy ka naam
        copy_name = new_name or f"Copy of {original.name}"
        
        # New file node — same content hash (deduplication!)
        copy = File(name=copy_name, owner_id=copied_by, mime_type=original.mime_type)
        
        if original.current_version:
            # Same hash reference — no new bytes stored!
            copy.add_version(
                content_hash=original.current_version.content_hash,
                size_bytes=original.current_version.size_bytes,
                uploaded_by=copied_by,
                change_summary=f"Copied from {original.name}"
            )
            # Reference count badhao
            self.content_store._ref_counts[original.current_version.content_hash] = (
                self.content_store._ref_counts.get(original.current_version.content_hash, 0) + 1
            )
        
        dest_folder.add_child(copy)
        self._nodes[copy.node_id] = copy
        
        print(f"[Drive] Copied: '{original.name}' → '{copy_name}' in '{dest_folder.name}'")
        return copy
    
    # ---- Delete ----
    
    def delete_node(self, node_id: str, deleted_by: str, permanent: bool = False):
        """
        Soft delete: trash mein jaao (30 din)
        Hard delete: storage se bhi hatao
        """
        node = self._get_node(node_id)
        
        if not node.can_write(deleted_by):
            raise PermissionError("No permission to delete")
        
        if permanent:
            # Content store se release karo
            if isinstance(node, File) and node.current_version:
                self.content_store.release(node.current_version.content_hash)
            
            # Parent se remove karo
            if node.parent_id:
                parent = self._nodes.get(node.parent_id)
                if parent and isinstance(parent, Folder):
                    parent.remove_child(node_id)
            
            del self._nodes[node_id]
            print(f"[Drive] PERMANENTLY deleted: '{node.name}'")
        else:
            # Soft delete → trash
            if node.parent_id:
                parent = self._nodes.get(node.parent_id)
                if parent and isinstance(parent, Folder):
                    parent.remove_child(node_id)
            
            self._trash[node_id] = (node, datetime.now())
            print(f"[Drive] Moved to trash: '{node.name}' (30 days to restore)")
    
    def restore_from_trash(self, node_id: str, dest_folder_id: str) -> FileNode:
        """Trash se restore karo"""
        if node_id not in self._trash:
            raise ValueError(f"Node {node_id} not in trash")
        
        node, deleted_at = self._trash.pop(node_id)
        dest_folder = self._get_node(dest_folder_id, Folder)
        dest_folder.add_child(node)
        
        print(f"[Drive] Restored: '{node.name}' to '{dest_folder.name}'")
        return node
    
    # ---- Search ----
    
    def search(self, user_id: str, query: str) -> List[FileNode]:
        """User ki files mein search karo"""
        root = self.get_root(user_id)
        results = root.find_recursive(query)
        
        # Permission filter (shared folders ke children bhi include karo)
        accessible = [r for r in results if r.can_read(user_id)]
        
        print(f"[Drive] Search '{query}': {len(accessible)} results")
        return accessible
    
    # ---- Share ----
    
    def share_file(self, node_id: str, shared_by: str, target_user: str,
                   level: PermissionLevel, can_reshare: bool = False):
        """File/folder share karo"""
        node = self._get_node(node_id)
        
        if not node.can_share(shared_by):
            raise PermissionError("No permission to share")
        
        node.grant_permission(target_user, level, shared_by, can_reshare)
        print(f"[Drive] Shared: '{node.name}' with {target_user} ({level.value})")
    
    def get_shareable_link(self, node_id: str, requested_by: str,
                           scope: SharingScope = SharingScope.ANYONE_WITH_LINK) -> str:
        """Shareable link generate karo"""
        node = self._get_node(node_id)
        
        if not node.can_share(requested_by):
            raise PermissionError("No permission to share")
        
        node.sharing_scope = scope
        link = f"https://drive.example.com/d/{node_id}"
        print(f"[Drive] Shareable link: {link} ({scope.value})")
        return link
    
    # ---- Version History ----
    
    def get_version_history(self, file_id: str, requesting_user: str) -> List[FileVersion]:
        file_node = self._get_node(file_id, File)
        
        if not file_node.can_read(requesting_user):
            raise PermissionError("No read permission")
        
        return file_node.get_version_history()
    
    def restore_version(self, file_id: str, version_id: str, restored_by: str) -> FileVersion:
        file_node = self._get_node(file_id, File)
        
        if not file_node.can_write(restored_by):
            raise PermissionError("No write permission")
        
        version = file_node.restore_version(version_id, restored_by)
        print(f"[Drive] Version restored: '{file_node.name}' → v{version.version_number}")
        return version
    
    # ---- Quota ----
    
    def get_quota(self, user_id: str) -> StorageQuota:
        return self._quotas.get(user_id)
    
    # ---- Tree View ----
    
    def print_tree(self, node: FileNode, indent: int = 0):
        """Debug: tree structure print karo"""
        prefix = "  " * indent
        
        if isinstance(node, Folder):
            size_str = self._human_readable(node.get_size())
            print(f"{prefix}📁 {node.name}/ ({size_str})")
            for child in node.list_children():
                self.print_tree(child, indent + 1)
        else:
            file = node
            size = file.current_version.size_bytes if file.current_version else 0
            version = file.current_version.version_number if file.current_version else 0
            print(f"{prefix}📄 {file.name} ({self._human_readable(size)}, v{version})")
    
    # ---- Helpers ----
    
    def _get_node(self, node_id: str, expected_type=None) -> FileNode:
        node = self._nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        if expected_type and not isinstance(node, expected_type):
            type_name = "file" if expected_type == File else "folder"
            raise ValueError(f"Node {node_id} is not a {type_name}")
        return node
    
    @staticmethod
    def _human_readable(bytes_val: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024:
                return f"{bytes_val:.0f} {unit}"
            bytes_val //= 1024
        return f"{bytes_val:.0f} TB"

# ===== DEMO =====

def demo():
    print("=" * 60)
    print("FILE STORAGE SYSTEM (GOOGLE DRIVE) DEMO")
    print("=" * 60)
    
    service = StorageService()
    
    # --- Setup ---
    print("\n--- User Setup ---")
    ashish_root = service.create_user_storage("ashish", quota_bytes=1024*1024*100)  # 100MB
    priya_root = service.create_user_storage("priya", quota_bytes=1024*1024*50)
    
    # --- Create Folder Structure ---
    print("\n--- Create Folders ---")
    work = service.create_folder(ashish_root.node_id, "Work", "ashish")
    personal = service.create_folder(ashish_root.node_id, "Personal", "ashish")
    projects = service.create_folder(work.node_id, "Projects", "ashish")
    
    # --- Upload Files ---
    print("\n--- Upload Files ---")
    resume = service.upload_file(
        work.node_id, "resume.pdf",
        b"PDF content for resume v1",
        "ashish", mime_type="application/pdf"
    )
    
    notes = service.upload_file(
        personal.node_id, "notes.txt",
        b"My personal notes",
        "ashish", mime_type="text/plain"
    )
    
    # --- Deduplication Demo ---
    print("\n--- Deduplication Demo ---")
    # Same content as resume in a different folder
    resume_copy = service.upload_file(
        projects.node_id, "resume_backup.pdf",
        b"PDF content for resume v1",  # Same bytes!
        "ashish", mime_type="application/pdf"
    )
    print(f"  Dedup: resume.pdf and resume_backup.pdf share same content in storage")
    
    # --- Versioning ---
    print("\n--- Versioning ---")
    service.upload_file(
        work.node_id, "resume.pdf",
        b"PDF content for resume v2 - updated skills",
        "ashish", change_summary="Added new skills section"
    )
    
    history = service.get_version_history(resume.node_id, "ashish")
    print(f"  Version history for resume.pdf:")
    for v in history:
        print(f"    v{v.version_number}: {v.change_summary} ({v.size_bytes} bytes)")
    
    # --- File Tree ---
    print("\n--- File Tree ---")
    service.print_tree(ashish_root)
    
    # --- Download ---
    print("\n--- Download ---")
    content = service.download_file(resume.node_id, "ashish")
    print(f"  Downloaded: {content[:30]}...")
    
    # --- Sharing ---
    print("\n--- Sharing ---")
    service.share_file(work.node_id, "ashish", "priya", PermissionLevel.VIEWER)
    
    # Priya can now read Work folder
    can_read = work.can_read("priya")
    can_write = work.can_write("priya")
    print(f"  Priya can read Work: {can_read}, can write: {can_write}")
    
    link = service.get_shareable_link(notes.node_id, "ashish")
    
    # --- Search ---
    print("\n--- Search ---")
    results = service.search("ashish", "resume")
    for r in results:
        print(f"  Found: {r.name}")
    
    # --- Quota ---
    print("\n--- Storage Quota ---")
    quota = service.get_quota("ashish")
    print(f"  Used: {quota.human_readable_used()} / {quota.human_readable_total()} "
          f"({quota.usage_percentage:.1f}%)")
    
    # Content store stats
    print(f"  Actual storage (after dedup): {service.content_store.get_total_unique_size()} bytes")
    
    # --- Delete + Restore ---
    print("\n--- Soft Delete + Restore ---")
    service.delete_node(notes.node_id, "ashish")
    service.restore_from_trash(notes.node_id, personal.node_id)
    
    print("\n[Demo Complete]")

if __name__ == "__main__":
    demo()
```

### 1.5 Tumhara real project mein kahan use hua

**Niroskos Document Management:**
- E-way bills, invoices, booking vouchers — sab storage mein hote the
- S3 mein store karte the with content hash as key (exact same deduplication pattern)
- Permissions: customer can view their own documents, subsidiary can view all

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> File Storage System manages hierarchical file organization using the Composite Pattern (File and Folder share a uniform FileNode interface), content-addressable storage for deduplication (SHA256 hash as storage key — identical files stored once), permission inheritance, and automatic versioning. Key trade-off: logical file tree vs physical content store are decoupled.

### 2.2 Composite Pattern

```
FileNode (abstract)
├── File (leaf)     — has content, versions
└── Folder (composite) — has children: List[FileNode]
    ├── File
    └── Folder
        └── File

get_size():
- File: current_version.size_bytes
- Folder: sum(child.get_size() for child in children)   ← recursive!

This means: drive.get_size() = total size of entire drive
```

### 2.3 Content-Addressable Storage (Deduplication)

```python
# Why SHA256?
# - Deterministic: same content → always same hash
# - Collision-resistant: different content → (almost certainly) different hash
# - 256-bit: 2^256 possible hashes → birthday collision probability negligible

# How deduplication works:
File A upload: "Hello World" → SHA256 = "abc123" → stored in content_store["abc123"]
File B upload: "Hello World" → SHA256 = "abc123" → content_store["abc123"] already exists!
                                                     ref_count["abc123"] += 1
                                                     NO bytes written to disk!

# Savings:
1M users share the same 10MB PDF → 10MB stored (not 10GB)
Deduplication ratio = logical_size / physical_size = 10GB/10MB = 1000x

# Reference counting for GC:
File A deleted → ref_count["abc123"] = 0 → garbage collected
File B still exists → ref_count["abc123"] = 1 → NOT deleted
```

### 2.4 Permission Model

```
Inheritance: Folder permission → applies to all children
Override: Child can have different permission than parent

Levels:
OWNER  → CRUD + Share + Delete + Transfer ownership
EDITOR → CRUD (no delete of others' files)
COMMENTER → Read + Add comments
VIEWER → Read only

Special rules:
- Public/Anyone-with-link → can_read() returns True without permission check
- Expiring permissions: perm.expiry → automatically revoked after date
- can_share flag: editor can share only if granted (default False)
```

### 2.5 Real Project Answer

> "In Niroskos, we stored booking documents — invoices, e-way bills, vouchers — in AWS S3 using content-addressable approach: the S3 key was SHA256 of the file content. This gave us automatic deduplication — multiple bookings for the same package used the same template PDF. Permissions mapped to our RBAC system: customers could download their own invoices (VIEWER), subsidiaries could access all documents for their bookings (EDITOR), admin had full access (OWNER). The versioning concept maps to our e-way bill amendments — each amendment creates a new version record pointing to new content."

### 2.6 Common Follow-up Q&A

**Q1: How does Google Drive handle 15 billion files efficiently?**
> "Metadata (file tree, permissions, version history) lives in a distributed SQL/Spanner database. Actual file content lives in GCS (Google Cloud Storage) with content hash as key. The separation means metadata queries (search, list) hit an indexed database, not blob storage. Index: user_id + parent_id + name for folder listing. Elasticsearch for full-text search across file names and document content."

**Q2: How do you handle concurrent edits (Google Docs real-time)?**
> "That's Operational Transform (OT) or CRDT — beyond file storage. For binary files, we use pessimistic locking: file.locked_by, file.lock_expires. If user A has a lock, user B gets 'read-only' access. For Google Docs-style collaboration, OT merges concurrent changes by transforming operations against each other. I'd implement this as a separate CollaborationService on top of the storage layer."

**Q3: How would you implement move vs copy at scale?**
> "Move: only update parent_id in metadata — no content bytes moved. O(1). Copy: create new File node pointing to same content_hash (no bytes copied) — O(1) metadata write. This is why Google Drive copy is instant even for large files — content not duplicated."

**Q4: How do you handle the 30-day trash retention?**
> "A background cron job runs daily: SELECT * FROM trash WHERE deleted_at < NOW() - INTERVAL '30 days'. For each expired item, it decrements the content hash reference count. When ref_count drops to 0, content is deleted from S3. This is batch garbage collection. Real Google Drive uses a more sophisticated lifecycle policy directly in GCS."

---

## Interview Cheat Sheet

```
30-second pitch:
"File storage uses Composite Pattern — File (leaf) and Folder (container) 
both implement FileNode. Content-addressable storage: SHA256 hash is the 
storage key — identical files stored once (deduplication). Permission model: 
OWNER > EDITOR > COMMENTER > VIEWER. Versioning: every upload adds a new 
FileVersion pointing to content hash. Delete = soft (trash 30 days) or hard 
(content ref_count → 0 → GC)."

Key numbers:
- SHA256: 256-bit hash, 64 hex chars
- Versions retained: last 100 (Google Drive) or unlimited (Dropbox)
- Trash retention: 30 days
- Free quota: 15GB (Google)

Patterns:
- Composite (File + Folder = FileNode)
- Strategy (different storage backends: local/S3/GCS)
- Observer (sync events when file changes)
- Repository (ContentStore: hash → bytes)
```
