# Library Management System LLD

## Quick Reference Card
```
Pattern Used    → Strategy (search), Observer (due-date alerts), State Machine (book lifecycle)
Core Challenge  → Concurrency (same book multiple copies), Fine calculation, Reservation queue
Key Classes     → Book, BookItem, Member, Loan, Reservation, LibraryService
State Machine   → AVAILABLE → RESERVED → BORROWED → LOST/DAMAGED
Interview Hook  → "Book aur BookItem ka difference — ek book ke multiple physical copies"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Library system mein sabse important insight hai:

**Book ≠ BookItem**
- **Book** = Concept / Catalog entry (ISBN, title, author, genre)
  - E.g., "Clean Code by Robert Martin" — yeh ek book hai
- **BookItem** = Physical copy (barcode, shelf location, condition)
  - E.g., "Clean Code — Copy #3, Shelf B-12, Barcode: LC001234"

Jaise ek song (Book) ke multiple CDs (BookItem) hoti hain.

**Core operations:**
1. Book search karo (by title/author/ISBN/genre)
2. Book borrow karo (available copy milni chahiye)
3. Book return karo (fine calculate karo)
4. Book reserve karo (sab copies out hain, waiting list)
5. Fine pay karo

### 1.2 Kab use karo?

- Physical library management
- Digital asset lending (e-books, courses)
- Tool/equipment lending systems
- Anything with "limited copies, reservation queue, due dates"

### 1.3 Kab mat use karo?

- Digital-only library (no copies concept, infinite downloads)
- Simple inventory without lending (bookstore)

### 1.4 Code — Hinglish comments ke saath

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Deque
from datetime import date, timedelta
from collections import deque, defaultdict
import threading
import uuid

# ===== ENUMS =====

class BookStatus(Enum):
    # Shelf pe hai, koi le sakta hai
    AVAILABLE = "AVAILABLE"
    # Kisi ke paas hai abhi
    BORROWED = "BORROWED"
    # Kisi ne reserve kiya hai, wapas aayi to us member ko milegi
    RESERVED = "RESERVED"
    # Member ne kho diya — fine + replacement cost
    LOST = "LOST"
    # Damaged — repair ke liye
    DAMAGED = "DAMAGED"
    # Out of circulation
    RETIRED = "RETIRED"

class MemberStatus(Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"   # Fine pending hai
    EXPIRED = "EXPIRED"       # Membership khatam

class SearchType(Enum):
    TITLE = "TITLE"
    AUTHOR = "AUTHOR"
    ISBN = "ISBN"
    GENRE = "GENRE"
    KEYWORD = "KEYWORD"      # Title + description mein search

# ===== BOOK (Catalog Entry) =====

@dataclass
class Book:
    """
    Abstract concept — ek book ka idea
    ISBN globally unique hota hai
    """
    isbn: str
    title: str
    author: str
    genre: str
    publisher: str
    year: int
    description: str = ""
    
    def __hash__(self):
        return hash(self.isbn)
    
    def __eq__(self, other):
        return isinstance(other, Book) and self.isbn == other.isbn

@dataclass
class BookItem:
    """
    Physical copy — ek book ka ek instance
    Barcode = unique ID per copy
    """
    barcode: str = field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    isbn: str = ""           # Kis book ka copy hai
    shelf_location: str = ""  # E.g., "B-12-3" (Row B, Shelf 12, Position 3)
    status: BookStatus = BookStatus.AVAILABLE
    condition: str = "GOOD"   # GOOD, FAIR, POOR
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    
    def is_available(self) -> bool:
        return self.status == BookStatus.AVAILABLE

# ===== MEMBER =====

@dataclass
class Member:
    """
    Library member — borrow/reserve kar sakta hai
    """
    member_id: str = field(default_factory=lambda: f"M{str(uuid.uuid4())[:6].upper()}")
    name: str = ""
    email: str = ""
    phone: str = ""
    membership_expiry: date = field(default_factory=lambda: date.today() + timedelta(days=365))
    status: MemberStatus = MemberStatus.ACTIVE
    total_fine_pending: float = 0.0
    
    # Rules
    MAX_BORROW_LIMIT = 5          # Ek saath 5 books
    MAX_RESERVATION_LIMIT = 3     # 3 reservations
    
    def can_borrow(self) -> tuple[bool, str]:
        if self.status == MemberStatus.SUSPENDED:
            return False, f"Account suspended. Pending fine: ₹{self.total_fine_pending}"
        if self.status == MemberStatus.EXPIRED:
            return False, "Membership expired. Please renew."
        if self.total_fine_pending > 100:  # ₹100 se zyada fine → suspend
            return False, f"Fine too high: ₹{self.total_fine_pending}. Pay first."
        return True, "OK"

# ===== LOAN =====

@dataclass
class Loan:
    """
    Ek borrow transaction — book kab li, kab return karni hai, kab ki
    """
    loan_id: str = field(default_factory=lambda: f"L{str(uuid.uuid4())[:8].upper()}")
    member_id: str = ""
    barcode: str = ""              # BookItem ka barcode
    isbn: str = ""
    borrow_date: date = field(default_factory=date.today)
    due_date: date = field(default_factory=lambda: date.today() + timedelta(days=14))
    return_date: Optional[date] = None
    fine_amount: float = 0.0
    fine_paid: bool = False
    
    DAILY_FINE_RATE = 2.0          # ₹2 per day overdue
    MAX_FINE_PER_BOOK = 200.0      # Maximum ₹200 fine per book
    LOAN_PERIOD_DAYS = 14
    
    def calculate_fine(self, return_date: date = None) -> float:
        """
        Fine calculate karo — agar return_date nahi diya, aaj ki date use karo
        """
        check_date = return_date or date.today()
        
        if check_date <= self.due_date:
            return 0.0  # On time return
        
        overdue_days = (check_date - self.due_date).days
        fine = overdue_days * self.DAILY_FINE_RATE
        return min(fine, self.MAX_FINE_PER_BOOK)
    
    @property
    def is_overdue(self) -> bool:
        if self.return_date:
            return False  # Already returned
        return date.today() > self.due_date
    
    @property
    def days_overdue(self) -> int:
        if not self.is_overdue:
            return 0
        return (date.today() - self.due_date).days

# ===== RESERVATION =====

@dataclass
class Reservation:
    """
    Book abhi available nahi — queue mein wait karo
    """
    reservation_id: str = field(default_factory=lambda: f"R{str(uuid.uuid4())[:8].upper()}")
    member_id: str = ""
    isbn: str = ""
    reserved_date: date = field(default_factory=date.today)
    expiry_date: date = field(default_factory=lambda: date.today() + timedelta(days=3))
    notified: bool = False      # Member ko notification gaya?
    
    def is_expired(self) -> bool:
        return date.today() > self.expiry_date

# ===== SEARCH STRATEGY =====

class SearchStrategy:
    """Strategy pattern — alag alag ways se search karo"""
    
    def search(self, catalog: Dict[str, Book], query: str) -> List[Book]:
        raise NotImplementedError

class TitleSearchStrategy(SearchStrategy):
    def search(self, catalog, query):
        q = query.lower()
        return [book for book in catalog.values() if q in book.title.lower()]

class AuthorSearchStrategy(SearchStrategy):
    def search(self, catalog, query):
        q = query.lower()
        return [book for book in catalog.values() if q in book.author.lower()]

class ISBNSearchStrategy(SearchStrategy):
    def search(self, catalog, query):
        book = catalog.get(query)
        return [book] if book else []

class GenreSearchStrategy(SearchStrategy):
    def search(self, catalog, query):
        q = query.lower()
        return [book for book in catalog.values() if q in book.genre.lower()]

class KeywordSearchStrategy(SearchStrategy):
    """Title + description + author mein search"""
    def search(self, catalog, query):
        q = query.lower()
        results = []
        for book in catalog.values():
            if (q in book.title.lower() or
                q in book.author.lower() or
                q in book.description.lower() or
                q in book.genre.lower()):
                results.append(book)
        return results

class SearchStrategyFactory:
    _strategies = {
        SearchType.TITLE: TitleSearchStrategy(),
        SearchType.AUTHOR: AuthorSearchStrategy(),
        SearchType.ISBN: ISBNSearchStrategy(),
        SearchType.GENRE: GenreSearchStrategy(),
        SearchType.KEYWORD: KeywordSearchStrategy(),
    }
    
    @classmethod
    def get(cls, search_type: SearchType) -> SearchStrategy:
        return cls._strategies[search_type]

# ===== NOTIFICATION SERVICE (Observer) =====

class NotificationObserver:
    """Book available hone par member ko notify karo"""
    
    def notify_book_available(self, member: Member, book: Book):
        print(f"  [Notification] SMS to {member.phone}: "
              f"'{book.title}' is now available. "
              f"Pick up within 3 days or reservation expires.")
    
    def notify_due_soon(self, member: Member, loan: Loan, book: Book):
        print(f"  [Notification] Email to {member.email}: "
              f"'{book.title}' due in {(loan.due_date - date.today()).days} days.")
    
    def notify_overdue(self, member: Member, loan: Loan, book: Book):
        print(f"  [Notification] Email to {member.email}: "
              f"OVERDUE — '{book.title}' {loan.days_overdue} days late. "
              f"Fine: ₹{loan.calculate_fine()}")

# ===== CATALOG (Book Registry) =====

class Catalog:
    """
    Books aur BookItems ka registry
    Thread-safe operations
    """
    
    def __init__(self):
        # isbn → Book
        self._books: Dict[str, Book] = {}
        # isbn → List[BookItem]
        self._book_items: Dict[str, List[BookItem]] = defaultdict(list)
        # barcode → BookItem (quick lookup)
        self._barcode_index: Dict[str, BookItem] = {}
        self._lock = threading.RLock()
    
    def add_book(self, book: Book):
        with self._lock:
            self._books[book.isbn] = book
    
    def add_book_item(self, item: BookItem):
        with self._lock:
            self._book_items[item.isbn].append(item)
            self._barcode_index[item.barcode] = item
    
    def get_book(self, isbn: str) -> Optional[Book]:
        return self._books.get(isbn)
    
    def get_book_item(self, barcode: str) -> Optional[BookItem]:
        return self._barcode_index.get(barcode)
    
    def get_available_copy(self, isbn: str) -> Optional[BookItem]:
        """Ek available copy dhundo — thread-safe"""
        with self._lock:
            for item in self._book_items.get(isbn, []):
                if item.is_available():
                    return item
        return None
    
    def get_available_count(self, isbn: str) -> int:
        return sum(1 for item in self._book_items.get(isbn, [])
                   if item.is_available())
    
    def get_total_copies(self, isbn: str) -> int:
        return len(self._book_items.get(isbn, []))
    
    def search(self, query: str, search_type: SearchType) -> List[Book]:
        strategy = SearchStrategyFactory.get(search_type)
        return strategy.search(self._books, query)

# ===== LIBRARY SERVICE (Facade) =====

class LibraryService:
    """
    Main facade — sab kuch yahan se access karo
    
    Business rules:
    1. Member max 5 books borrow kar sakta hai
    2. Loan period = 14 days
    3. Fine = ₹2/day, max ₹200/book
    4. Fine > ₹100 → account suspend
    5. Reservation expiry = 3 days after notification
    6. Reserved book → sirf us member ko milegi
    """
    
    def __init__(self):
        self.catalog = Catalog()
        # member_id → Member
        self._members: Dict[str, Member] = {}
        # loan_id → Loan
        self._loans: Dict[str, Loan] = {}
        # member_id → List[Loan] (active loans)
        self._active_loans: Dict[str, List[Loan]] = defaultdict(list)
        # isbn → Deque[Reservation] (FIFO queue per book)
        self._reservations: Dict[str, Deque[Reservation]] = defaultdict(deque)
        # member_id → List[Reservation]
        self._member_reservations: Dict[str, List[Reservation]] = defaultdict(list)
        
        self._notifier = NotificationObserver()
        self._lock = threading.RLock()
    
    # ---- Member Management ----
    
    def register_member(self, name: str, email: str, phone: str) -> Member:
        member = Member(name=name, email=email, phone=phone)
        self._members[member.member_id] = member
        print(f"[Library] Member registered: {member.member_id} — {member.name}")
        return member
    
    def get_member(self, member_id: str) -> Optional[Member]:
        return self._members.get(member_id)
    
    # ---- Catalog ----
    
    def add_book(self, book: Book) -> Book:
        self.catalog.add_book(book)
        print(f"[Library] Book added to catalog: {book.isbn} — {book.title}")
        return book
    
    def add_book_copy(self, isbn: str, shelf_location: str, condition: str = "GOOD") -> BookItem:
        book = self.catalog.get_book(isbn)
        if not book:
            raise ValueError(f"Book {isbn} not in catalog")
        
        item = BookItem(isbn=isbn, shelf_location=shelf_location, condition=condition)
        self.catalog.add_book_item(item)
        print(f"[Library] Copy added: {item.barcode} → '{book.title}' at {shelf_location}")
        return item
    
    def search_books(self, query: str, search_type: SearchType = SearchType.KEYWORD) -> List[Book]:
        results = self.catalog.search(query, search_type)
        print(f"[Library] Search '{query}' ({search_type.value}): {len(results)} results")
        return results
    
    # ---- Borrow ----
    
    def borrow_book(self, member_id: str, isbn: str) -> Loan:
        """
        Book borrow karo
        
        Steps:
        1. Member valid hai?
        2. Member borrow limit check
        3. Available copy hai?
        4. Reserved hai to kisi aur ke liye? → reject
        5. BookItem status update
        6. Loan create karo
        """
        with self._lock:
            # 1. Member check
            member = self._members.get(member_id)
            if not member:
                raise ValueError(f"Member {member_id} not found")
            
            can_borrow, reason = member.can_borrow()
            if not can_borrow:
                raise PermissionError(reason)
            
            # 2. Borrow limit
            active = self._active_loans.get(member_id, [])
            if len(active) >= Member.MAX_BORROW_LIMIT:
                raise PermissionError(f"Borrow limit reached ({Member.MAX_BORROW_LIMIT} books max)")
            
            # 3. Available copy
            item = self.catalog.get_available_copy(isbn)
            if not item:
                # Check reservation status
                queue = self._reservations.get(isbn, deque())
                available_count = self.catalog.get_available_count(isbn)
                total = self.catalog.get_total_copies(isbn)
                raise ValueError(
                    f"No copies available. Total: {total}, Available: {available_count}, "
                    f"Queue length: {len(queue)}. Use reserve_book() to join waitlist."
                )
            
            # 4. Reservation check — agar reserved hai, sirf us member ko milegi
            queue = self._reservations.get(isbn, deque())
            if queue:
                next_reservation = queue[0]
                if next_reservation.member_id != member_id:
                    # Book reserved hai kisi aur ke liye
                    if not next_reservation.is_expired():
                        raise PermissionError(
                            f"Book reserved for another member. "
                            f"Join waitlist with reserve_book()."
                        )
                    else:
                        # Reservation expire ho gayi, remove karo
                        queue.popleft()
            
            # 5. BookItem mark as borrowed
            with item._lock:
                item.status = BookStatus.BORROWED
            
            # 6. Remove reservation if this member had one
            if queue and queue[0].member_id == member_id:
                reservation = queue.popleft()
                self._member_reservations[member_id] = [
                    r for r in self._member_reservations[member_id]
                    if r.reservation_id != reservation.reservation_id
                ]
            
            # 7. Create loan
            loan = Loan(
                member_id=member_id,
                barcode=item.barcode,
                isbn=isbn,
                due_date=date.today() + timedelta(days=Loan.LOAN_PERIOD_DAYS)
            )
            self._loans[loan.loan_id] = loan
            self._active_loans[member_id].append(loan)
            
            book = self.catalog.get_book(isbn)
            print(f"[Library] BORROWED: '{book.title}' → {member.name} "
                  f"| Due: {loan.due_date} | Loan: {loan.loan_id}")
            return loan
    
    # ---- Return ----
    
    def return_book(self, barcode: str, member_id: str) -> dict:
        """
        Book return karo
        
        Returns dict with fine_amount, loan details
        """
        with self._lock:
            # Active loan dhundo
            active = self._active_loans.get(member_id, [])
            loan = next((l for l in active if l.barcode == barcode), None)
            
            if not loan:
                raise ValueError(f"No active loan found for barcode {barcode} and member {member_id}")
            
            # Return date set karo
            loan.return_date = date.today()
            
            # Fine calculate karo
            fine = loan.calculate_fine(loan.return_date)
            loan.fine_amount = fine
            
            # Member ka fine update karo
            member = self._members[member_id]
            if fine > 0:
                member.total_fine_pending += fine
                if member.total_fine_pending > 100:
                    member.status = MemberStatus.SUSPENDED
                    print(f"  [Library] Account SUSPENDED — fine ₹{member.total_fine_pending}")
            
            # Active loan se remove karo
            self._active_loans[member_id] = [l for l in active if l.barcode != barcode]
            
            # BookItem status update
            item = self.catalog.get_book_item(barcode)
            book = self.catalog.get_book(item.isbn)
            
            # Check karo koi reservation queue mein hai?
            queue = self._reservations.get(item.isbn, deque())
            
            # Expired reservations clean karo
            while queue and queue[0].is_expired():
                queue.popleft()
            
            if queue:
                # Reservation hai → RESERVED status, notify karo
                next_reservation = queue[0]
                item.status = BookStatus.RESERVED
                next_member = self._members.get(next_reservation.member_id)
                if next_member:
                    next_reservation.notified = True
                    next_reservation.expiry_date = date.today() + timedelta(days=3)
                    self._notifier.notify_book_available(next_member, book)
                    print(f"  [Library] Book reserved for {next_member.name} — 3 days to pick up")
            else:
                # Koi reservation nahi → AVAILABLE
                item.status = BookStatus.AVAILABLE
            
            result = {
                "loan_id": loan.loan_id,
                "book_title": book.title,
                "return_date": loan.return_date,
                "fine_amount": fine,
                "fine_paid": loan.fine_paid,
                "member_status": member.status.value
            }
            
            print(f"[Library] RETURNED: '{book.title}' by {member.name} "
                  f"| Fine: ₹{fine} | Status: {member.status.value}")
            return result
    
    # ---- Reserve ----
    
    def reserve_book(self, member_id: str, isbn: str) -> Reservation:
        """
        Book available nahi → waiting list join karo
        """
        with self._lock:
            member = self._members.get(member_id)
            if not member:
                raise ValueError(f"Member {member_id} not found")
            
            # Pehle check karo available hai to
            if self.catalog.get_available_count(isbn) > 0:
                raise ValueError("Book is currently available. Use borrow_book() instead.")
            
            # Already reserved by this member?
            queue = self._reservations[isbn]
            if any(r.member_id == member_id for r in queue):
                raise ValueError("Already in reservation queue for this book")
            
            # Max reservation limit
            if len(self._member_reservations.get(member_id, [])) >= Member.MAX_RESERVATION_LIMIT:
                raise PermissionError(f"Reservation limit reached ({Member.MAX_RESERVATION_LIMIT})")
            
            reservation = Reservation(member_id=member_id, isbn=isbn)
            queue.append(reservation)
            self._member_reservations[member_id].append(reservation)
            
            book = self.catalog.get_book(isbn)
            queue_position = len(queue)
            print(f"[Library] RESERVED: '{book.title}' → {member.name} "
                  f"| Queue position: {queue_position} | ID: {reservation.reservation_id}")
            return reservation
    
    # ---- Fine Payment ----
    
    def pay_fine(self, member_id: str, amount: float) -> dict:
        """Fine payment"""
        member = self._members.get(member_id)
        if not member:
            raise ValueError(f"Member {member_id} not found")
        
        if amount > member.total_fine_pending:
            amount = member.total_fine_pending  # Zyada payment → cap karo
        
        member.total_fine_pending -= amount
        member.total_fine_pending = round(member.total_fine_pending, 2)
        
        # Suspend hatao agar fine clear
        if member.total_fine_pending <= 0 and member.status == MemberStatus.SUSPENDED:
            member.status = MemberStatus.ACTIVE
            print(f"  [Library] Account REACTIVATED — fine cleared")
        
        print(f"[Library] FINE PAID: ₹{amount} by {member.name} "
              f"| Remaining: ₹{member.total_fine_pending}")
        
        return {
            "member_id": member_id,
            "amount_paid": amount,
            "remaining_fine": member.total_fine_pending,
            "account_status": member.status.value
        }
    
    # ---- Reports / Queries ----
    
    def get_member_loans(self, member_id: str) -> List[Loan]:
        return self._active_loans.get(member_id, [])
    
    def get_overdue_loans(self) -> List[Loan]:
        overdue = []
        for loans in self._active_loans.values():
            overdue.extend(l for l in loans if l.is_overdue)
        return overdue
    
    def get_book_availability(self, isbn: str) -> dict:
        book = self.catalog.get_book(isbn)
        if not book:
            return {"error": "Book not found"}
        
        queue = self._reservations.get(isbn, deque())
        return {
            "isbn": isbn,
            "title": book.title,
            "total_copies": self.catalog.get_total_copies(isbn),
            "available": self.catalog.get_available_count(isbn),
            "reservation_queue": len(queue),
            "expected_wait_days": len(queue) * Loan.LOAN_PERIOD_DAYS
        }
    
    def send_due_date_reminders(self):
        """Cron job — 2 din pehle reminder bhejo"""
        reminder_threshold = date.today() + timedelta(days=2)
        for loans in self._active_loans.values():
            for loan in loans:
                if loan.due_date <= reminder_threshold and not loan.is_overdue:
                    member = self._members[loan.member_id]
                    book = self.catalog.get_book(loan.isbn)
                    self._notifier.notify_due_soon(member, loan, book)

# ===== DEMO =====

def demo():
    print("=" * 60)
    print("LIBRARY MANAGEMENT SYSTEM DEMO")
    print("=" * 60)
    
    lib = LibraryService()
    
    # --- Catalog Setup ---
    print("\n--- Setting up catalog ---")
    clean_code = lib.add_book(Book(
        isbn="978-0132350884",
        title="Clean Code",
        author="Robert C. Martin",
        genre="Software Engineering",
        publisher="Prentice Hall",
        year=2008,
        description="Handbook of agile software craftsmanship"
    ))
    
    design_patterns = lib.add_book(Book(
        isbn="978-0201633610",
        title="Design Patterns",
        author="Gang of Four",
        genre="Software Engineering",
        publisher="Addison-Wesley",
        year=1994,
        description="Elements of reusable object-oriented software"
    ))
    
    # 2 copies of Clean Code, 1 of Design Patterns
    lib.add_book_copy("978-0132350884", "A-01-1")
    lib.add_book_copy("978-0132350884", "A-01-2")
    lib.add_book_copy("978-0201633610", "A-02-1")
    
    # --- Members ---
    print("\n--- Registering members ---")
    ashish = lib.register_member("Ashish Kumar", "ashish@email.com", "+91-9999999999")
    priya = lib.register_member("Priya Sharma", "priya@email.com", "+91-8888888888")
    rahul = lib.register_member("Rahul Singh", "rahul@email.com", "+91-7777777777")
    
    # --- Search ---
    print("\n--- Search Demo ---")
    results = lib.search_books("Clean", SearchType.TITLE)
    for r in results:
        print(f"  Found: {r.title} by {r.author}")
    
    results = lib.search_books("Martin", SearchType.AUTHOR)
    for r in results:
        print(f"  Found: {r.title} by {r.author}")
    
    # --- Borrow ---
    print("\n--- Borrow Demo ---")
    loan1 = lib.borrow_book(ashish.member_id, "978-0132350884")
    loan2 = lib.borrow_book(priya.member_id, "978-0132350884")  # 2nd copy
    
    # Design Patterns borrow karo
    loan3 = lib.borrow_book(rahul.member_id, "978-0201633610")
    
    # --- Availability Check ---
    print("\n--- Availability Check ---")
    avail = lib.get_book_availability("978-0132350884")
    print(f"  Clean Code: {avail['available']}/{avail['total_copies']} available, "
          f"Queue: {avail['reservation_queue']}")
    
    # --- Reservation ---
    print("\n--- Reservation Demo ---")
    try:
        # Koi copy available nahi (both borrowed)
        lib.reserve_book(rahul.member_id, "978-0132350884")
    except ValueError as e:
        print(f"  Error: {e}")
    
    # Design Patterns pe reservation (woh bhi borrowed hai)
    lib.reserve_book(ashish.member_id, "978-0201633610")
    lib.reserve_book(priya.member_id, "978-0201633610")
    
    # --- Return with Fine ---
    print("\n--- Return with Overdue Fine ---")
    # Manually set loan as overdue for demo
    loan3.borrow_date = date.today() - timedelta(days=20)
    loan3.due_date = date.today() - timedelta(days=6)  # 6 days overdue
    
    result = lib.return_book(loan3.barcode, rahul.member_id)
    print(f"  Fine amount: ₹{result['fine_amount']}")
    
    # Return triggers notification to next in queue (Ashish)
    # Ashish had reserved Design Patterns
    
    # --- Fine Payment ---
    print("\n--- Fine Payment ---")
    lib.pay_fine(rahul.member_id, 10.0)
    lib.pay_fine(rahul.member_id, 2.0)  # Remaining 2 rupees
    
    # --- Overdue Report ---
    print("\n--- Overdue Loans ---")
    # Set loan1 as overdue for demo
    loan1.due_date = date.today() - timedelta(days=3)
    overdue = lib.get_overdue_loans()
    for l in overdue:
        book = lib.catalog.get_book(l.isbn)
        member = lib.get_member(l.member_id)
        print(f"  OVERDUE: '{book.title}' — {member.name} "
              f"({l.days_overdue} days, fine ₹{l.calculate_fine()})")
    
    print("\n[Demo Complete]")

if __name__ == "__main__":
    demo()
```

### 1.5 Tumhara real project mein kahan use hua

**Booking System → Library ka booking concept:**
- `Package (Book)` — abstract product concept
- `PackageInventory (BookItem)` — physical seat/slot
- `Booking (Loan)` — ek specific booking transaction  
- `WaitingList (Reservation)` — package full, queue join karo

**Fine → Niroskos cancellation charges:**
```python
def calculate_cancellation_charge(booking, cancel_date):
    days_before_travel = (booking.travel_date - cancel_date).days
    if days_before_travel >= 7:
        return 0.0          # Free cancellation
    elif days_before_travel >= 3:
        return booking.amount * 0.25   # 25% charge
    else:
        return booking.amount * 0.50   # 50% charge
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> Library Management System manages the lifecycle of physical books — from catalog management to lending, reservations, and fine calculation. The key architectural insight is separating **Book** (abstract catalog entry with ISBN) from **BookItem** (physical copy with barcode and shelf location), allowing multiple concurrent loans of the same title.

### 2.2 Key Design Insight: Book vs BookItem

```
Book (ISBN: 978-0132350884)
├── BookItem (Barcode: A1B2C3, Shelf: A-01-1, Status: BORROWED by Ashish)
├── BookItem (Barcode: D4E5F6, Shelf: A-01-2, Status: AVAILABLE)
└── BookItem (Barcode: G7H8I9, Shelf: A-01-3, Status: RESERVED for Priya)

Reservation Queue for this ISBN:
[Priya → Rahul → Shyam]  (FIFO)
```

### 2.3 Key Components

| Component | Responsibility | Design Pattern |
|-----------|---------------|----------------|
| `Book` | Catalog entry (ISBN, metadata) | Value Object |
| `BookItem` | Physical copy (barcode, status) | Entity |
| `Loan` | Borrow transaction + fine | Entity |
| `Reservation` | Waitlist entry with expiry | Entity |
| `Catalog` | Book + BookItem registry | Repository |
| `SearchStrategy` | Pluggable search algorithms | Strategy |
| `NotificationObserver` | Alerts on events | Observer |
| `LibraryService` | All operations facade | Facade |

### 2.4 Fine Calculation Logic

```python
def calculate_fine(self, return_date: date) -> float:
    if return_date <= self.due_date:
        return 0.0
    
    overdue_days = (return_date - self.due_date).days
    fine = overdue_days * 2.0           # ₹2/day
    return min(fine, 200.0)             # Cap at ₹200
```

**Cascading effects:**
1. Fine calculated on return
2. Added to member.total_fine_pending
3. If total > ₹100 → member.status = SUSPENDED
4. Suspended member cannot borrow
5. Pay fine → fine cleared → account reactivated

### 2.5 Reservation + Availability Flow

```
return_book(barcode, member_id)
    │
    ├─→ calculate fine
    ├─→ active_loans remove
    └─→ check reservation queue for this ISBN
            │
            ├─→ Queue empty? → BookItem.status = AVAILABLE
            │
            └─→ Queue has entries?
                    │
                    ├─→ First entry expired? → remove, check next
                    └─→ Valid reservation found?
                            ├─→ BookItem.status = RESERVED
                            ├─→ Update expiry = today + 3 days
                            └─→ notify_book_available(next_member, book)
```

### 2.6 Concurrency: Same Book, Multiple Borrowers

```python
# Race condition: two members try to borrow last copy simultaneously
# Thread A: get_available_copy() → finds copy #1 (AVAILABLE)
# Thread B: get_available_copy() → finds copy #1 (still AVAILABLE)
# Both proceed to borrow → double booking!

# Solution: RLock in LibraryService.borrow_book()
def borrow_book(self, member_id, isbn):
    with self._lock:                    # Only one thread at a time
        item = self.catalog.get_available_copy(isbn)
        if not item:
            raise ValueError("No copies available")
        
        with item._lock:                # Item-level lock for status change
            item.status = BookStatus.BORROWED
        
        loan = Loan(...)                # Create loan record
        ...
```

### 2.7 Search Strategy Pattern

```python
# Add new search type without changing existing code (Open/Closed Principle)
class PublisherSearchStrategy(SearchStrategy):
    def search(self, catalog, query):
        q = query.lower()
        return [b for b in catalog.values() if q in b.publisher.lower()]

# Register it
SearchStrategyFactory._strategies[SearchType.PUBLISHER] = PublisherSearchStrategy()
# Zero changes to LibraryService or Catalog
```

### 2.8 Real Project Answer

> "In my Niroskos project at Youngman Infotech, we had a similar pattern for tour package management. A 'Package' was like our Book — it defined the product. 'PackageDeparture' was like BookItem — a specific departure date slot. When a slot was fully booked, customers joined a waitlist. On cancellation, the next customer was notified and given 24 hours to confirm. The fine calculation maps to our cancellation charge policy — the later you cancel, the higher the charge. Both enforce time-based sliding penalties."

### 2.9 Common Follow-up Q&A

**Q1: How do you handle concurrent borrow requests for the last copy?**
> "I use a reentrant lock (RLock) at the service level for the entire borrow transaction. Within the lock: check availability → update BookItem status → create Loan record. This check-and-act is atomic. For distributed systems (multiple server instances), I'd use a Redis distributed lock with a SET NX EX command, same as our payment idempotency implementation."

**Q2: What if a member never returns a book?**
> "The Loan has a 'lost_reported' flag. If overdue > 30 days and no contact, librarian marks it LOST: BookItem status → LOST, fine = max_fine (₹200) + replacement cost (book price). Member account → SUSPENDED. The book item is retired from circulation. A new copy must be added if needed. Similar to our Niroskos booking no-show policy."

**Q3: How would you add e-book support?**
> "I'd use the same Book catalog with a format field (PHYSICAL, EBOOK, AUDIOBOOK). EBookItem would extend BookItem with download_url and concurrent_loan_limit (say, 3 — one book can be borrowed by 3 members simultaneously). The Loan logic stays the same but availability check changes: for ebooks, available = current_loans < concurrent_limit instead of status == AVAILABLE."

**Q4: How to prevent a member from repeatedly renewing to avoid return?**
> "MAX_RENEWALS_ALLOWED = 2. After 2 renewals, forced return. Also, if a reservation queue exists for that book, renewals are blocked — someone is waiting. The LoanExtension entity tracks renewal count and prevents abuse."

**Q5: Database schema for this?**

```sql
CREATE TABLE books (isbn VARCHAR PRIMARY KEY, title, author, genre, publisher, year);

CREATE TABLE book_items (
    barcode VARCHAR PRIMARY KEY,
    isbn VARCHAR REFERENCES books(isbn),
    shelf_location VARCHAR,
    status VARCHAR,
    condition VARCHAR
);

CREATE TABLE members (
    member_id VARCHAR PRIMARY KEY,
    name, email, phone,
    membership_expiry DATE,
    status VARCHAR,
    total_fine_pending DECIMAL(10,2)
);

CREATE TABLE loans (
    loan_id VARCHAR PRIMARY KEY,
    member_id VARCHAR REFERENCES members,
    barcode VARCHAR REFERENCES book_items,
    borrow_date DATE, due_date DATE, return_date DATE,
    fine_amount DECIMAL(10,2),
    fine_paid BOOLEAN DEFAULT FALSE
);

CREATE TABLE reservations (
    reservation_id VARCHAR PRIMARY KEY,
    member_id VARCHAR REFERENCES members,
    isbn VARCHAR REFERENCES books,
    reserved_date DATE,
    expiry_date DATE,
    position INT,   -- Queue position
    notified BOOLEAN DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_loans_member ON loans(member_id) WHERE return_date IS NULL;
CREATE INDEX idx_reservations_isbn ON reservations(isbn) WHERE expiry_date >= CURRENT_DATE;
CREATE INDEX idx_book_items_isbn_status ON book_items(isbn, status);
```

---

## Interview Cheat Sheet

```
30-second pitch:
"Library system has two key entities: Book (ISBN, metadata — the concept)
and BookItem (barcode, shelf location — physical copy). A Book can have
multiple BookItems. Borrowing locks a specific BookItem, reservation joins
a FIFO queue per ISBN. Fine = ₹2/day, capped at ₹200. On return,
next reservation is notified with 3-day pickup window."

Key business rules:
- Max 5 books borrowed simultaneously
- Max 3 active reservations
- Loan period = 14 days
- Fine = ₹2/day, max ₹200
- Fine > ₹100 → account suspended
- Reservation expiry = 3 days after notification

Patterns:
- Strategy (search: title/author/isbn/genre/keyword)
- Observer (notifications on return, due date)
- Facade (LibraryService hides all complexity)
- State Machine (BookItem: AVAILABLE→BORROWED→RESERVED→LOST)
- Repository (Catalog: single source of truth for books)
```
