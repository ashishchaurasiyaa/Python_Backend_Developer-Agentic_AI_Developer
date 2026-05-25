# Tic Tac Toe / Chess / Board Games LLD

## Quick Reference Card
```
Pattern Used    → Strategy (game rules/win condition), State Machine (game phases), Command (move history)
Core Challenge  → Extensible for different board games, Win detection, Move validation
Key Classes     → Board, Player, Game, MoveValidator, WinChecker
Interview Hook  → "Abstract Board + Strategy Pattern = same code works for Tic Tac Toe, Connect 4, Chess"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Board game LLD ka goal hai: **extensible design** jo Tic Tac Toe se shuru hoke Chess tak scale ho sake.

**Key abstractions:**
- `Board` — grid, pieces manage karta hai
- `Player` — kaun khel raha hai
- `MoveValidator` — yeh move valid hai?
- `WinChecker` — koi jeeta?
- `Game` — sab ko orchestrate karta hai

**Tic Tac Toe vs Chess:**
- Same structure, alag validators + win checkers
- Strategy pattern se swap ho jaate hain

### 1.2 Code — Tic Tac Toe (Primary) + Chess Skeleton

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from abc import ABC, abstractmethod
import uuid

# ===== ENUMS =====

class GameStatus(Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DRAW = "DRAW"
    PAUSED = "PAUSED"

class PieceType(Enum):
    # Tic Tac Toe
    X = "X"
    O = "O"
    EMPTY = " "
    
    # Chess pieces
    PAWN = "P"
    ROOK = "R"
    KNIGHT = "N"
    BISHOP = "B"
    QUEEN = "Q"
    KING = "K"

class PieceColor(Enum):
    WHITE = "WHITE"
    BLACK = "BLACK"
    NONE = "NONE"

# ===== PIECE =====

@dataclass
class Piece:
    piece_type: PieceType
    color: PieceColor = PieceColor.NONE
    symbol: str = " "
    
    def __str__(self):
        return self.symbol
    
    def is_empty(self) -> bool:
        return self.piece_type == PieceType.EMPTY

EMPTY_PIECE = Piece(PieceType.EMPTY, PieceColor.NONE, " ")
X_PIECE = Piece(PieceType.X, PieceColor.NONE, "X")
O_PIECE = Piece(PieceType.O, PieceColor.NONE, "O")

# ===== CELL =====

@dataclass
class Cell:
    row: int
    col: int
    piece: Piece = field(default_factory=lambda: EMPTY_PIECE)
    
    def is_empty(self) -> bool:
        return self.piece.is_empty()
    
    def place(self, piece: Piece):
        self.piece = piece
    
    def clear(self):
        self.piece = EMPTY_PIECE

# ===== MOVE =====

@dataclass
class Move:
    move_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    player_id: str = ""
    from_row: int = -1      # Tic Tac Toe: always -1 (no source)
    from_col: int = -1
    to_row: int = 0
    to_col: int = 0
    piece: Piece = None
    captured_piece: Optional[Piece] = None
    is_valid: bool = False
    
    def __str__(self):
        return f"({self.to_row},{self.to_col})"

# ===== BOARD =====

class Board:
    """
    Generic board — any size grid
    Works for 3x3 (Tic Tac Toe), 8x8 (Chess), 6x7 (Connect 4)
    """
    
    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self._grid: List[List[Cell]] = [
            [Cell(r, c) for c in range(cols)]
            for r in range(rows)
        ]
    
    def get_cell(self, row: int, col: int) -> Cell:
        if not self.is_valid_position(row, col):
            raise ValueError(f"Invalid position: ({row}, {col})")
        return self._grid[row][col]
    
    def place_piece(self, row: int, col: int, piece: Piece):
        self.get_cell(row, col).place(piece)
    
    def get_piece(self, row: int, col: int) -> Piece:
        return self.get_cell(row, col).piece
    
    def is_valid_position(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols
    
    def is_cell_empty(self, row: int, col: int) -> bool:
        return self.get_cell(row, col).is_empty()
    
    def get_all_cells(self) -> List[Cell]:
        return [cell for row in self._grid for cell in row]
    
    def print_board(self):
        """ASCII board print karo"""
        # Column numbers
        col_header = "   " + "  ".join(str(c) for c in range(self.cols))
        print(col_header)
        
        separator = "  " + "+---" * self.cols + "+"
        print(separator)
        
        for r in range(self.rows):
            row_str = f"{r} |"
            for c in range(self.cols):
                piece = self.get_piece(r, c)
                row_str += f" {piece.symbol} |"
            print(row_str)
            print(separator)

# ===== PLAYER =====

@dataclass
class Player:
    player_id: str = field(default_factory=lambda: f"P{str(uuid.uuid4())[:6].upper()}")
    name: str = ""
    piece: Piece = None
    wins: int = 0
    losses: int = 0
    draws: int = 0
    
    def __str__(self):
        return f"{self.name} ({self.piece.symbol})"

# ===== MOVE VALIDATOR (Strategy) =====

class MoveValidator(ABC):
    """Strategy — different games ka alag validation"""
    
    @abstractmethod
    def is_valid_move(self, board: Board, move: Move, player: Player) -> tuple[bool, str]:
        pass

class TicTacToeMoveValidator(MoveValidator):
    """
    Rules:
    1. Position board ke andar honi chahiye
    2. Cell empty honi chahiye
    """
    
    def is_valid_move(self, board, move, player):
        row, col = move.to_row, move.to_col
        
        if not board.is_valid_position(row, col):
            return False, f"Position ({row},{col}) is out of bounds"
        
        if not board.is_cell_empty(row, col):
            return False, f"Position ({row},{col}) is already occupied"
        
        return True, "Valid"

class Connect4MoveValidator(MoveValidator):
    """
    Connect 4: sirf column specify karo, piece gravity se gira"""
    
    def is_valid_move(self, board, move, player):
        col = move.to_col
        
        if not (0 <= col < board.cols):
            return False, "Invalid column"
        
        # Column full?
        if not board.is_cell_empty(0, col):
            return False, f"Column {col} is full"
        
        # Find bottom-most empty row
        for row in range(board.rows - 1, -1, -1):
            if board.is_cell_empty(row, col):
                move.to_row = row  # Set actual row
                return True, "Valid"
        
        return False, "Column full"

# ===== WIN CHECKER (Strategy) =====

class WinChecker(ABC):
    @abstractmethod
    def check_win(self, board: Board, last_move: Move) -> Optional[str]:
        """Returns winner's player_id or None"""
        pass
    
    @abstractmethod
    def check_draw(self, board: Board) -> bool:
        pass

class TicTacToeWinChecker(WinChecker):
    """
    3x3 Tic Tac Toe:
    - 3 in a row (horizontal)
    - 3 in a column (vertical)
    - 3 in a diagonal
    """
    
    def check_win(self, board, last_move):
        piece = last_move.piece
        r, c = last_move.to_row, last_move.to_col
        n = board.rows  # 3 for standard TTT
        
        # Check row
        if all(board.get_piece(r, col).symbol == piece.symbol for col in range(n)):
            return last_move.player_id
        
        # Check column
        if all(board.get_piece(row, c).symbol == piece.symbol for row in range(n)):
            return last_move.player_id
        
        # Check main diagonal (top-left to bottom-right)
        if r == c:
            if all(board.get_piece(i, i).symbol == piece.symbol for i in range(n)):
                return last_move.player_id
        
        # Check anti-diagonal (top-right to bottom-left)
        if r + c == n - 1:
            if all(board.get_piece(i, n-1-i).symbol == piece.symbol for i in range(n)):
                return last_move.player_id
        
        return None
    
    def check_draw(self, board):
        """All cells filled → draw"""
        return all(not cell.is_empty() for cell in board.get_all_cells())

class NxNWinChecker(WinChecker):
    """Generalized win checker for NxN board — win requires N in a row"""
    
    def __init__(self, win_length: int):
        self.win_length = win_length
    
    def check_win(self, board, last_move):
        piece = last_move.piece
        r, c = last_move.to_row, last_move.to_col
        
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]  # horiz, vert, diag, anti-diag
        
        for dr, dc in directions:
            count = 1  # Count current cell
            
            # Forward direction
            for step in range(1, self.win_length):
                nr, nc = r + dr * step, c + dc * step
                if (board.is_valid_position(nr, nc) and
                        board.get_piece(nr, nc).symbol == piece.symbol):
                    count += 1
                else:
                    break
            
            # Backward direction
            for step in range(1, self.win_length):
                nr, nc = r - dr * step, c - dc * step
                if (board.is_valid_position(nr, nc) and
                        board.get_piece(nr, nc).symbol == piece.symbol):
                    count += 1
                else:
                    break
            
            if count >= self.win_length:
                return last_move.player_id
        
        return None
    
    def check_draw(self, board):
        return all(not cell.is_empty() for cell in board.get_all_cells())

# ===== MOVE HISTORY (Command Pattern) =====

class MoveHistory:
    """
    Command pattern: undo support + game replay
    """
    
    def __init__(self):
        self._moves: List[Move] = []
    
    def record(self, move: Move):
        self._moves.append(move)
    
    def undo_last(self) -> Optional[Move]:
        if self._moves:
            return self._moves.pop()
        return None
    
    def get_all_moves(self) -> List[Move]:
        return list(self._moves)
    
    def get_last_move(self) -> Optional[Move]:
        return self._moves[-1] if self._moves else None

# ===== GAME =====

class Game:
    """
    Orchestrator — board game ka pura lifecycle
    
    Works for any game by swapping:
    - MoveValidator
    - WinChecker
    """
    
    def __init__(self, board: Board, players: List[Player],
                 validator: MoveValidator, win_checker: WinChecker):
        self.game_id = str(uuid.uuid4())[:8]
        self.board = board
        self.players = players
        self.validator = validator
        self.win_checker = win_checker
        self.history = MoveHistory()
        
        self.status = GameStatus.NOT_STARTED
        self._current_player_idx = 0
        self._winner: Optional[Player] = None
    
    @property
    def current_player(self) -> Player:
        return self.players[self._current_player_idx]
    
    @property
    def winner(self) -> Optional[Player]:
        return self._winner
    
    def start(self):
        self.status = GameStatus.IN_PROGRESS
        print(f"\n[Game {self.game_id}] Started!")
        print(f"Players: {' vs '.join(str(p) for p in self.players)}")
        self.board.print_board()
        print(f"\n{self.current_player.name}'s turn")
    
    def make_move(self, row: int, col: int) -> tuple[bool, str]:
        """
        Move attempt karo
        Returns: (success, message)
        """
        if self.status != GameStatus.IN_PROGRESS:
            return False, f"Game is not in progress (status: {self.status.value})"
        
        player = self.current_player
        
        move = Move(
            player_id=player.player_id,
            to_row=row,
            to_col=col,
            piece=player.piece
        )
        
        # Validate
        is_valid, reason = self.validator.is_valid_move(self.board, move, player)
        if not is_valid:
            return False, f"Invalid move: {reason}"
        
        move.is_valid = True
        
        # Apply move
        self.board.place_piece(move.to_row, move.to_col, player.piece)
        self.history.record(move)
        
        print(f"\n{player.name} plays ({move.to_row},{move.to_col})")
        self.board.print_board()
        
        # Check win
        winner_id = self.win_checker.check_win(self.board, move)
        if winner_id:
            winner_player = next(p for p in self.players if p.player_id == winner_id)
            self._winner = winner_player
            self.status = GameStatus.COMPLETED
            winner_player.wins += 1
            for p in self.players:
                if p.player_id != winner_id:
                    p.losses += 1
            print(f"\n*** {winner_player.name} WINS! ***")
            return True, f"{winner_player.name} wins!"
        
        # Check draw
        if self.win_checker.check_draw(self.board):
            self.status = GameStatus.DRAW
            for p in self.players:
                p.draws += 1
            print("\n*** DRAW! ***")
            return True, "Draw!"
        
        # Next player's turn
        self._current_player_idx = (self._current_player_idx + 1) % len(self.players)
        print(f"{self.current_player.name}'s turn")
        return True, "Move accepted"
    
    def undo_move(self) -> bool:
        """Last move undo karo"""
        if self.status != GameStatus.IN_PROGRESS:
            return False
        
        last_move = self.history.undo_last()
        if not last_move:
            return False
        
        # Board pe piece hata do
        self.board.get_cell(last_move.to_row, last_move.to_col).clear()
        
        # Previous player ki turn
        self._current_player_idx = (self._current_player_idx - 1) % len(self.players)
        
        print(f"\n[Undo] {self.current_player.name}'s move undone")
        self.board.print_board()
        return True
    
    def resign(self, player_id: str) -> str:
        """Player resign karta hai"""
        resigning_player = next((p for p in self.players if p.player_id == player_id), None)
        if not resigning_player:
            return "Player not found"
        
        self.status = GameStatus.COMPLETED
        resigning_player.losses += 1
        
        winner = next(p for p in self.players if p.player_id != player_id)
        winner.wins += 1
        self._winner = winner
        
        print(f"\n{resigning_player.name} resigned. {winner.name} wins!")
        return f"{winner.name} wins by resignation"

# ===== GAME FACTORY =====

class GameFactory:
    """
    Factory — game type se Game object create karo
    """
    
    @staticmethod
    def create_tic_tac_toe(player1_name: str, player2_name: str) -> Game:
        board = Board(3, 3)
        
        p1 = Player(name=player1_name, piece=X_PIECE)
        p2 = Player(name=player2_name, piece=O_PIECE)
        
        validator = TicTacToeMoveValidator()
        win_checker = TicTacToeWinChecker()
        
        return Game(board, [p1, p2], validator, win_checker)
    
    @staticmethod
    def create_5x5_tic_tac_toe(player1_name: str, player2_name: str,
                                win_length: int = 4) -> Game:
        """5x5 board, win requires 4 in a row"""
        board = Board(5, 5)
        
        p1 = Player(name=player1_name, piece=X_PIECE)
        p2 = Player(name=player2_name, piece=O_PIECE)
        
        validator = TicTacToeMoveValidator()
        win_checker = NxNWinChecker(win_length)
        
        return Game(board, [p1, p2], validator, win_checker)
    
    @staticmethod
    def create_connect4(player1_name: str, player2_name: str) -> Game:
        """Connect 4: 6 rows x 7 cols, 4 in a row to win"""
        board = Board(6, 7)
        
        p1 = Player(name=player1_name, piece=Piece(PieceType.X, PieceColor.NONE, "●"))
        p2 = Player(name=player2_name, piece=Piece(PieceType.O, PieceColor.NONE, "○"))
        
        validator = Connect4MoveValidator()
        win_checker = NxNWinChecker(4)
        
        return Game(board, [p1, p2], validator, win_checker)

# ===== CHESS SKELETON (for interview context) =====

class ChessPiece(Piece):
    """Chess piece — har piece ka alag movement rules"""
    
    def get_valid_moves(self, board: Board, row: int, col: int) -> List[Tuple[int, int]]:
        raise NotImplementedError

class Pawn(ChessPiece):
    def get_valid_moves(self, board, row, col):
        moves = []
        direction = -1 if self.color == PieceColor.WHITE else 1  # White goes up (row--)
        
        # Forward one step
        if board.is_valid_position(row + direction, col):
            if board.is_cell_empty(row + direction, col):
                moves.append((row + direction, col))
                
                # Initial 2-step move
                starting_row = 6 if self.color == PieceColor.WHITE else 1
                if row == starting_row and board.is_cell_empty(row + 2*direction, col):
                    moves.append((row + 2*direction, col))
        
        # Diagonal capture
        for dc in [-1, 1]:
            nr, nc = row + direction, col + dc
            if board.is_valid_position(nr, nc):
                piece = board.get_piece(nr, nc)
                if not piece.is_empty() and piece.color != self.color:
                    moves.append((nr, nc))
        
        return moves

class Rook(ChessPiece):
    def get_valid_moves(self, board, row, col):
        moves = []
        # Horizontal + Vertical
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            r, c = row + dr, col + dc
            while board.is_valid_position(r, c):
                piece = board.get_piece(r, c)
                if piece.is_empty():
                    moves.append((r, c))
                elif piece.color != self.color:
                    moves.append((r, c))  # Can capture
                    break
                else:
                    break  # Own piece blocks
                r += dr
                c += dc
        return moves

class ChessMoveValidator(MoveValidator):
    def is_valid_move(self, board, move, player):
        # Source cell mein player ka piece hona chahiye
        source_piece = board.get_piece(move.from_row, move.from_col)
        
        if source_piece.is_empty():
            return False, "No piece at source"
        if source_piece.color != player.piece.color:
            return False, "Not your piece"
        
        if not isinstance(source_piece, ChessPiece):
            return False, "Invalid piece type"
        
        valid_moves = source_piece.get_valid_moves(board, move.from_row, move.from_col)
        if (move.to_row, move.to_col) not in valid_moves:
            return False, "Invalid move for this piece"
        
        return True, "Valid"
    
    def check_win(self, board, last_move):
        # King capture check
        for r in range(board.rows):
            for c in range(board.cols):
                piece = board.get_piece(r, c)
                if (piece.piece_type == PieceType.KING and
                        piece.color != last_move.piece.color):
                    return None  # King still alive
        return last_move.player_id  # King captured

# ===== DEMO =====

def demo():
    print("=" * 50)
    print("TIC TAC TOE DEMO")
    print("=" * 50)
    
    # Standard Tic Tac Toe
    game = GameFactory.create_tic_tac_toe("Ashish", "Priya")
    game.start()
    
    # Ashish wins: X in diagonal
    moves = [
        (0, 0),  # Ashish X
        (1, 0),  # Priya O
        (0, 1),  # Ashish X
        (1, 1),  # Priya O
        (0, 2),  # Ashish X → wins top row!
    ]
    
    for i, (r, c) in enumerate(moves):
        success, msg = game.make_move(r, c)
        if game.status == GameStatus.COMPLETED:
            break
    
    # Stats
    print(f"\nFinal status: {game.status.value}")
    for p in game.players:
        print(f"  {p.name}: W{p.wins} L{p.losses} D{p.draws}")
    
    # Undo demo
    print("\n" + "=" * 50)
    print("UNDO DEMO (5x5 Board)")
    print("=" * 50)
    
    game2 = GameFactory.create_5x5_tic_tac_toe("Alice", "Bob", win_length=4)
    game2.start()
    
    game2.make_move(0, 0)   # Alice
    game2.make_move(1, 1)   # Bob
    game2.make_move(0, 1)   # Alice
    
    print("\n--- Undo Alice's last move ---")
    game2.undo_move()
    
    print("\n[Demo Complete]")

if __name__ == "__main__":
    demo()
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> Board game LLD demonstrates open extensibility: the same `Game` class with the same lifecycle (start → make_move → check_win → check_draw) works for Tic Tac Toe, Connect 4, and Chess by swapping `MoveValidator` and `WinChecker` strategies. The `Board` is a generic N×M grid. Move history uses the Command pattern for undo support.

### 2.2 Key Abstractions

| Component | Responsibility | Pattern |
|-----------|---------------|---------|
| `Board(N, M)` | Grid management | — |
| `MoveValidator` | Is this move legal? | Strategy |
| `WinChecker` | Did someone win? | Strategy |
| `MoveHistory` | Record + undo moves | Command |
| `Game` | Lifecycle orchestration | Facade |
| `GameFactory` | Create game instances | Factory |

### 2.3 Win Detection — O(1) Approach

```python
# Naive: check entire board after every move → O(N²)
# Better: only check row/col/diag through the LAST MOVE → O(N)

def check_win(self, board, last_move):
    r, c = last_move.to_row, last_move.to_col
    piece = last_move.piece
    n = board.rows
    
    # Row: O(N)
    if all(board.get_piece(r, col).symbol == piece.symbol for col in range(n)):
        return last_move.player_id
    
    # Col: O(N)
    if all(board.get_piece(row, c).symbol == piece.symbol for row in range(n)):
        return last_move.player_id
    
    # Diagonals: O(N)
    # Total: O(N) per move — not O(N²)
```

### 2.4 Extensibility Demo

```python
# Adding Connect 4 — zero changes to Game, Board, Player:
validator = Connect4MoveValidator()   # New validator
win_checker = NxNWinChecker(4)        # Reuse generalized checker
game = Game(Board(6,7), players, validator, win_checker)

# Adding Chess — zero changes to Game:
validator = ChessMoveValidator()
game = Game(Board(8,8), chess_players, validator, chess_win_checker)
```

### 2.5 N-Player Tic Tac Toe

```python
# 3-player TTT (3x3 board, 3 players X/O/△)
players = [
    Player(name="Alice", piece=X_PIECE),
    Player(name="Bob", piece=O_PIECE),
    Player(name="Carol", piece=Piece(PieceType.X, PieceColor.NONE, "△")),
]
# Game.make_move() already uses circular player cycling:
self._current_player_idx = (self._current_player_idx + 1) % len(self.players)
# Works for 2, 3, 4... players automatically
```

### 2.6 Common Follow-up Q&A

**Q1: How do you detect check/checkmate in Chess?**
> "After every move, check if the current player's king is attacked by any enemy piece — that's 'check'. To detect checkmate: generate all possible moves for the current player (checked player). If any move results in a board state where their king is NOT in check, it's not checkmate. If zero such moves exist, it's checkmate. This is O(M × N²) where M = number of pieces — acceptable for chess since M ≤ 32."

**Q2: How would you make this multiplayer over network?**
> "Move becomes a command object serialized as JSON: `{game_id, player_id, from, to, timestamp}`. REST endpoint `POST /game/{id}/move`. Server validates move, applies to board, persists game state (Redis for active games, DB for history). WebSocket or polling for real-time updates. Concurrent moves: game has a `current_turn` field — move rejected if it's not your turn."

**Q3: Why Command pattern for move history?**
> "Command pattern encapsulates a move as an object with all info needed to execute AND undo it. Undo: clear board cell, decrement player index. Redo: re-apply stored move. This enables full game replay (great for analysis) and limited undo (configurable max undos). Alternative: snapshot entire board on each move — simpler but O(N²) memory per move."

---

## Interview Cheat Sheet

```
30-second pitch:
"Board games use Strategy pattern: MoveValidator checks if move is legal,
WinChecker detects if someone won. Both are swappable — same Game class
handles Tic Tac Toe, Connect 4, Chess. Board is generic N×M grid.
Win detection is O(N) by only checking lines through the last move.
Command pattern enables undo via move history."

For Tic Tac Toe specifically:
- Win condition: 3 in a row/col/diagonal
- Check only on last played row/col/diag → O(N)
- Draw: all cells filled, no winner

Extension path:
TTT (3x3) → Larger TTT (NxN) → Connect 4 (gravity) → Chess (complex rules)
Each step = new Validator + new WinChecker. Game/Board unchanged.
```
