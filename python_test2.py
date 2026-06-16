"""オセロ（リバーシ）ゲーム

コンソールで遊べる2人対戦用オセロゲームです。
黒(●)が先手、白(○)が後手で交互に石を置きます。
"""

# 盤面のサイズ
SIZE = 8

# 石を表す定数
EMPTY = "."
BLACK = "●"
WHITE = "○"

# 8方向（縦・横・斜め）の移動量
DIRECTIONS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]


def create_board():
    """初期盤面を生成して返す。"""
    board = [[EMPTY for _ in range(SIZE)] for _ in range(SIZE)]
    # 中央4マスに初期配置
    board[3][3] = WHITE
    board[3][4] = BLACK
    board[4][3] = BLACK
    board[4][4] = WHITE
    return board


def opponent(stone):
    """相手の石の色を返す。"""
    return WHITE if stone == BLACK else BLACK


def on_board(row, col):
    """(row, col) が盤面内かどうかを判定する。"""
    return 0 <= row < SIZE and 0 <= col < SIZE


def stones_to_flip(board, row, col, stone):
    """(row, col) に stone を置いたときに裏返せる石の座標リストを返す。"""
    if board[row][col] != EMPTY:
        return []

    flips = []
    for dr, dc in DIRECTIONS:
        line = []
        r, c = row + dr, col + dc
        # 相手の石が続く間、候補として集める
        while on_board(r, c) and board[r][c] == opponent(stone):
            line.append((r, c))
            r += dr
            c += dc
        # 最後に自分の石で挟めていれば裏返し確定
        if line and on_board(r, c) and board[r][c] == stone:
            flips.extend(line)
    return flips


def valid_moves(board, stone):
    """stone が置ける全マスの座標リストを返す。"""
    moves = []
    for row in range(SIZE):
        for col in range(SIZE):
            if stones_to_flip(board, row, col, stone):
                moves.append((row, col))
    return moves


def place_stone(board, row, col, stone):
    """石を置き、挟んだ相手の石を裏返す。"""
    flips = stones_to_flip(board, row, col, stone)
    if not flips:
        return False
    board[row][col] = stone
    for r, c in flips:
        board[r][c] = stone
    return True


def count_stones(board):
    """(黒の数, 白の数) を返す。"""
    black = sum(row.count(BLACK) for row in board)
    white = sum(row.count(WHITE) for row in board)
    return black, white


def print_board(board):
    """盤面を見やすく表示する。"""
    print("\n   " + " ".join(str(c) for c in range(SIZE)))
    for r in range(SIZE):
        print(f" {r} " + " ".join(board[r]))
    black, white = count_stones(board)
    print(f"\n   黒(●): {black}   白(○): {white}\n")


def parse_input(text):
    """ユーザー入力 "行 列" を (row, col) に変換する。失敗時は None。"""
    parts = text.replace(",", " ").split()
    if len(parts) != 2:
        return None
    try:
        row, col = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not on_board(row, col):
        return None
    return row, col


def play():
    """ゲームのメインループ。"""
    board = create_board()
    current = BLACK
    print("=== オセロ（リバーシ） ===")
    print("入力形式: 「行 列」（例: 2 3）。終了は q。")

    while True:
        moves = valid_moves(board, current)
        # 現在のプレイヤーが置ける場所がない場合
        if not moves:
            # 相手も置けなければゲーム終了
            if not valid_moves(board, opponent(current)):
                break
            print(f"{current} は置ける場所がないためパスします。")
            current = opponent(current)
            continue

        print_board(board)
        print(f"手番: {current}  置ける場所: " +
              ", ".join(f"({r},{c})" for r, c in moves))

        text = input(f"{current} の手を入力してください > ").strip()
        if text.lower() == "q":
            print("ゲームを中断しました。")
            return

        pos = parse_input(text)
        if pos is None:
            print("入力が正しくありません。「行 列」の形式で入力してください。")
            continue

        row, col = pos
        if (row, col) not in moves:
            print("そこには置けません。置ける場所から選んでください。")
            continue

        place_stone(board, row, col, current)
        current = opponent(current)

    # 結果発表
    print_board(board)
    black, white = count_stones(board)
    print("=== ゲーム終了 ===")
    if black > white:
        print(f"黒(●) の勝ちです！ {black} 対 {white}")
    elif white > black:
        print(f"白(○) の勝ちです！ {white} 対 {black}")
    else:
        print(f"引き分けです。 {black} 対 {white}")


if __name__ == "__main__":
    play()
