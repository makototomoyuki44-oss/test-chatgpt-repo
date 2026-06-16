"""ブロック崩し（Breakout）ゲーム

tkinter で動く、見た目にこだわったブロック崩しゲームです。
追加ライブラリのインストールは不要で、標準の Python だけで動きます。

特徴:
- グラデーション風の背景と、虹色のブロック
- ブロックを壊したときのパーティクル風エフェクト
- 光沢のあるパドルとボール
- スコア / ライフ / レベル表示の HUD
- スタート画面・ゲームオーバー・クリア演出

操作方法:
- マウス移動 または 左右矢印キー でパドルを動かす
- スペース / クリック でボールを発射、ポーズ解除
- P でポーズ、R でリスタート
"""

import math
import random
import tkinter as tk

# ---- 画面・ゲームの基本設定 ----------------------------------------------
WIDTH = 720          # ウィンドウ幅
HEIGHT = 800         # ウィンドウ高さ
FPS = 60             # フレームレート
FRAME_MS = int(1000 / FPS)

# パドル
PADDLE_W = 120
PADDLE_H = 16
PADDLE_Y = HEIGHT - 70
PADDLE_SPEED = 12

# ボール
BALL_R = 9
BALL_SPEED = 6.0
BALL_SPEED_MAX = 12.0

# ブロック
BRICK_ROWS = 6
BRICK_COLS = 10
BRICK_TOP = 110
BRICK_GAP = 6
BRICK_H = 28
BRICK_SIDE_PAD = 30

# 色（行ごとの虹色グラデーション）
ROW_COLORS = [
    "#ff5252",  # 赤
    "#ff9800",  # オレンジ
    "#ffd600",  # 黄
    "#69f0ae",  # 緑
    "#40c4ff",  # 水
    "#b388ff",  # 紫
]
BG_TOP = (12, 16, 40)      # 背景グラデーション上
BG_BOTTOM = (40, 10, 60)   # 背景グラデーション下


def lerp_color(c1, c2, t):
    """2つの (r,g,b) を t (0..1) で線形補間して #rrggbb を返す。"""
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def shade(hex_color, factor):
    """#rrggbb を factor 倍して明るく/暗くする。"""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


class Brick:
    """1つのブロック。耐久(hits)があり、上の行ほど硬い。"""

    def __init__(self, x, y, w, h, color, hits):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.color = color
        self.hits = hits          # 残り耐久
        self.max_hits = hits
        self.alive = True

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


class Particle:
    """ブロック破壊時に飛び散る小さな破片。"""

    def __init__(self, x, y, color):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(2, 6)
        self.x = x
        self.y = y
        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd - 2
        self.life = random.uniform(0.4, 0.9)
        self.age = 0.0
        self.size = random.uniform(2, 5)
        self.color = color

    def update(self, dt):
        self.age += dt
        self.vy += 14 * dt  # 重力
        self.x += self.vx
        self.y += self.vy
        return self.age < self.life


class BreakoutGame:
    STATE_START = "start"
    STATE_READY = "ready"      # ボール発射待ち
    STATE_PLAY = "play"
    STATE_PAUSE = "pause"
    STATE_OVER = "over"
    STATE_CLEAR = "clear"

    def __init__(self, root):
        self.root = root
        self.root.title("✦ BREAKOUT ✦")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root, width=WIDTH, height=HEIGHT, highlightthickness=0, bg="#0c1028"
        )
        self.canvas.pack()

        # 背景グラデーションは一度だけ描いてキャッシュ
        self._draw_background()

        # 入力
        self.canvas.bind("<Motion>", self.on_mouse)
        root.bind("<Left>", lambda e: self._set_key("left", True))
        root.bind("<Right>", lambda e: self._set_key("right", True))
        root.bind("<KeyRelease-Left>", lambda e: self._set_key("left", False))
        root.bind("<KeyRelease-Right>", lambda e: self._set_key("right", False))
        root.bind("<space>", self.on_action)
        self.canvas.bind("<Button-1>", self.on_action)
        root.bind("<p>", self.toggle_pause)
        root.bind("<P>", self.toggle_pause)
        root.bind("<r>", lambda e: self.reset_game())
        root.bind("<R>", lambda e: self.reset_game())

        self.keys = {"left": False, "right": False}
        self.reset_game()
        self.loop()

    # ---- 初期化 ---------------------------------------------------------
    def reset_game(self):
        self.score = 0
        self.lives = 3
        self.level = 1
        self.combo = 0
        self.particles = []
        self.state = self.STATE_START
        self.paddle_x = WIDTH / 2
        self._build_level()
        self._reset_ball()

    def _build_level(self):
        self.bricks = []
        total_gap = BRICK_GAP * (BRICK_COLS - 1)
        usable = WIDTH - BRICK_SIDE_PAD * 2 - total_gap
        bw = usable / BRICK_COLS
        for row in range(BRICK_ROWS):
            color = ROW_COLORS[row % len(ROW_COLORS)]
            # 上の行ほど硬い（最大2〜3ヒット）。レベルが上がると硬くなる
            hits = 1 + (BRICK_ROWS - row) // 3 + (self.level - 1) // 2
            hits = min(hits, 3)
            for col in range(BRICK_COLS):
                x = BRICK_SIDE_PAD + col * (bw + BRICK_GAP)
                y = BRICK_TOP + row * (BRICK_H + BRICK_GAP)
                self.bricks.append(Brick(x, y, bw, BRICK_H, color, hits))

    def _reset_ball(self):
        self.ball_x = self.paddle_x
        self.ball_y = PADDLE_Y - BALL_R - 2
        # 上方向にやや斜めで発射準備
        ang = random.uniform(-0.4, 0.4) - math.pi / 2
        self.ball_vx = math.cos(ang) * BALL_SPEED
        self.ball_vy = math.sin(ang) * BALL_SPEED
        if self.state != self.STATE_START:
            self.state = self.STATE_READY

    # ---- 入力ハンドラ ---------------------------------------------------
    def _set_key(self, k, v):
        self.keys[k] = v

    def on_mouse(self, event):
        if self.state in (self.STATE_PLAY, self.STATE_READY):
            self.paddle_x = event.x

    def on_action(self, event=None):
        if self.state == self.STATE_START:
            self.state = self.STATE_READY
        elif self.state == self.STATE_READY:
            self.state = self.STATE_PLAY
        elif self.state == self.STATE_PAUSE:
            self.state = self.STATE_PLAY
        elif self.state in (self.STATE_OVER, self.STATE_CLEAR):
            self.reset_game()

    def toggle_pause(self, event=None):
        if self.state == self.STATE_PLAY:
            self.state = self.STATE_PAUSE
        elif self.state == self.STATE_PAUSE:
            self.state = self.STATE_PLAY

    # ---- メインループ ---------------------------------------------------
    def loop(self):
        dt = FRAME_MS / 1000.0
        self.update(dt)
        self.draw()
        self.root.after(FRAME_MS, self.loop)

    def update(self, dt):
        # パドルをキーボードでも動かせる
        if self.keys["left"]:
            self.paddle_x -= PADDLE_SPEED
        if self.keys["right"]:
            self.paddle_x += PADDLE_SPEED
        half = PADDLE_W / 2
        self.paddle_x = max(half, min(WIDTH - half, self.paddle_x))

        # パーティクル更新
        self.particles = [p for p in self.particles if p.update(dt)]

        if self.state == self.STATE_READY:
            # ボールはパドルに追従
            self.ball_x = self.paddle_x
            self.ball_y = PADDLE_Y - BALL_R - 2
            return

        if self.state != self.STATE_PLAY:
            return

        self._move_ball()

    def _move_ball(self):
        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy

        # 壁との反射
        if self.ball_x - BALL_R <= 0:
            self.ball_x = BALL_R
            self.ball_vx = abs(self.ball_vx)
        elif self.ball_x + BALL_R >= WIDTH:
            self.ball_x = WIDTH - BALL_R
            self.ball_vx = -abs(self.ball_vx)
        if self.ball_y - BALL_R <= 0:
            self.ball_y = BALL_R
            self.ball_vy = abs(self.ball_vy)

        # 下に落ちた → ミス
        if self.ball_y - BALL_R > HEIGHT:
            self.lives -= 1
            self.combo = 0
            if self.lives <= 0:
                self.state = self.STATE_OVER
            else:
                self._reset_ball()
            return

        self._check_paddle()
        self._check_bricks()

        # 全ブロック破壊 → クリア（次レベルへ）
        if all(not b.alive for b in self.bricks):
            self.level += 1
            self._build_level()
            self._reset_ball()
            self.state = self.STATE_CLEAR

    def _check_paddle(self):
        half = PADDLE_W / 2
        left = self.paddle_x - half
        right = self.paddle_x + half
        top = PADDLE_Y
        if (
            self.ball_vy > 0
            and self.ball_y + BALL_R >= top
            and self.ball_y - BALL_R <= top + PADDLE_H
            and left <= self.ball_x <= right
        ):
            # 当たった位置で反射角を変える（端ほど鋭角）
            offset = (self.ball_x - self.paddle_x) / half  # -1..1
            speed = min(math.hypot(self.ball_vx, self.ball_vy) + 0.1, BALL_SPEED_MAX)
            ang = -math.pi / 2 + offset * (math.pi / 3)  # 最大±60度
            self.ball_vx = math.cos(ang) * speed
            self.ball_vy = math.sin(ang) * speed
            self.ball_y = top - BALL_R - 1
            self.combo = 0

    def _check_bricks(self):
        bx, by = self.ball_x, self.ball_y
        for b in self.bricks:
            if not b.alive:
                continue
            # 円と矩形の当たり判定
            nearest_x = max(b.x, min(bx, b.x + b.w))
            nearest_y = max(b.y, min(by, b.y + b.h))
            dx = bx - nearest_x
            dy = by - nearest_y
            if dx * dx + dy * dy <= BALL_R * BALL_R:
                # どちらの面で当たったか（侵入量が小さい軸で反射）
                overlap_x = BALL_R - abs(dx)
                overlap_y = BALL_R - abs(dy)
                if overlap_x < overlap_y:
                    self.ball_vx = -self.ball_vx if dx == 0 else math.copysign(
                        abs(self.ball_vx), dx
                    )
                else:
                    self.ball_vy = -self.ball_vy if dy == 0 else math.copysign(
                        abs(self.ball_vy), dy
                    )

                b.hits -= 1
                self.combo += 1
                gain = 10 * self.level + self.combo * 2
                self.score += gain
                self._spawn_particles(b.cx, b.cy, b.color, 6 if b.hits <= 0 else 3)
                if b.hits <= 0:
                    b.alive = False
                # 1フレームに1ブロックだけ処理して安定させる
                break

    def _spawn_particles(self, x, y, color, n):
        for _ in range(n):
            self.particles.append(Particle(x, y, color))

    # ---- 背景 -----------------------------------------------------------
    def _draw_background(self):
        steps = 60
        h = HEIGHT / steps
        for i in range(steps):
            t = i / (steps - 1)
            color = lerp_color(BG_TOP, BG_BOTTOM, t)
            self.canvas.create_rectangle(
                0, i * h, WIDTH, (i + 1) * h + 1, fill=color, outline=color, tags="bg"
            )
        # うっすら星をちりばめる（背景の一部として固定）
        rng = random.Random(7)
        for _ in range(60):
            x = rng.randint(0, WIDTH)
            y = rng.randint(0, HEIGHT)
            r = rng.choice([1, 1, 2])
            c = rng.choice(["#ffffff", "#c5cae9", "#9fa8da"])
            self.canvas.create_oval(x, y, x + r, y + r, fill=c, outline="", tags="bg")

    # ---- 描画 -----------------------------------------------------------
    def draw(self):
        self.canvas.delete("dyn")  # 背景以外を消す

        self._draw_bricks()
        self._draw_particles()
        self._draw_paddle()
        self._draw_ball()
        self._draw_hud()

        if self.state == self.STATE_START:
            self._overlay("✦ BREAKOUT ✦",
                          "クリック / スペース でスタート\n"
                          "マウス・矢印キーでパドル操作 ・ P でポーズ")
        elif self.state == self.STATE_READY:
            self._hint("クリック / スペース でボール発射")
        elif self.state == self.STATE_PAUSE:
            self._overlay("PAUSE", "スペース / P で再開")
        elif self.state == self.STATE_OVER:
            self._overlay("GAME OVER",
                          f"スコア: {self.score}\nクリック / R でもう一度",
                          color="#ff5252")
        elif self.state == self.STATE_CLEAR:
            self._overlay(f"LEVEL {self.level - 1} CLEAR!",
                          "クリック / スペース で次のレベルへ",
                          color="#69f0ae")

    def _draw_bricks(self):
        for b in self.bricks:
            if not b.alive:
                continue
            # 耐久に応じて明るさを変える
            f = 0.55 + 0.45 * (b.hits / b.max_hits)
            face = shade(b.color, f)
            top = shade(b.color, min(1.6, f + 0.5))
            # 本体
            self.canvas.create_rectangle(
                b.x, b.y, b.x + b.w, b.y + b.h,
                fill=face, outline=shade(b.color, 0.4), width=1, tags="dyn"
            )
            # 上部のハイライト（光沢）
            self.canvas.create_rectangle(
                b.x + 2, b.y + 2, b.x + b.w - 2, b.y + b.h * 0.4,
                fill=top, outline="", tags="dyn"
            )

    def _draw_particles(self):
        for p in self.particles:
            a = 1 - p.age / p.life
            s = p.size * a
            self.canvas.create_oval(
                p.x - s, p.y - s, p.x + s, p.y + s,
                fill=shade(p.color, 0.7 + 0.3 * a), outline="", tags="dyn"
            )

    def _draw_paddle(self):
        half = PADDLE_W / 2
        x0, x1 = self.paddle_x - half, self.paddle_x + half
        y0, y1 = PADDLE_Y, PADDLE_Y + PADDLE_H
        # 影
        self.canvas.create_rectangle(
            x0 + 3, y0 + 4, x1 + 3, y1 + 4, fill="#05060f", outline="", tags="dyn"
        )
        # 本体（青系グラデ風）
        self.canvas.create_rectangle(
            x0, y0, x1, y1, fill="#42a5f5", outline="#e3f2fd", width=2, tags="dyn"
        )
        self.canvas.create_rectangle(
            x0 + 3, y0 + 2, x1 - 3, y0 + PADDLE_H * 0.45,
            fill="#90caf9", outline="", tags="dyn"
        )

    def _draw_ball(self):
        x, y = self.ball_x, self.ball_y
        # 影
        self.canvas.create_oval(
            x - BALL_R + 2, y - BALL_R + 3, x + BALL_R + 2, y + BALL_R + 3,
            fill="#05060f", outline="", tags="dyn"
        )
        # 本体
        self.canvas.create_oval(
            x - BALL_R, y - BALL_R, x + BALL_R, y + BALL_R,
            fill="#fff176", outline="#fffde7", width=2, tags="dyn"
        )
        # ハイライト
        self.canvas.create_oval(
            x - BALL_R * 0.5, y - BALL_R * 0.6, x, y - BALL_R * 0.1,
            fill="#ffffff", outline="", tags="dyn"
        )

    def _draw_hud(self):
        # 上部バー
        self.canvas.create_rectangle(
            0, 0, WIDTH, 48, fill="#0a0d20", outline="", tags="dyn"
        )
        self.canvas.create_text(
            20, 24, anchor="w", text=f"SCORE  {self.score}",
            fill="#ffd600", font=("Consolas", 18, "bold"), tags="dyn"
        )
        self.canvas.create_text(
            WIDTH / 2, 24, text=f"LEVEL {self.level}",
            fill="#40c4ff", font=("Consolas", 18, "bold"), tags="dyn"
        )
        # ライフをハート風の丸で表示
        self.canvas.create_text(
            WIDTH - 150, 24, anchor="w", text="LIVES",
            fill="#b0bec5", font=("Consolas", 14, "bold"), tags="dyn"
        )
        for i in range(self.lives):
            cx = WIDTH - 80 + i * 24
            self.canvas.create_oval(
                cx, 16, cx + 16, 32, fill="#ff5252", outline="#ffcdd2", tags="dyn"
            )
        if self.combo > 1:
            self.canvas.create_text(
                WIDTH / 2, 70, text=f"COMBO x{self.combo}",
                fill="#ffab40", font=("Consolas", 14, "bold"), tags="dyn"
            )

    def _overlay(self, title, subtitle, color="#ffffff"):
        # 半透明風（暗い板）に文字を乗せる
        self.canvas.create_rectangle(
            0, HEIGHT / 2 - 120, WIDTH, HEIGHT / 2 + 120,
            fill="#06081a", outline="", tags="dyn"
        )
        self.canvas.create_rectangle(
            0, HEIGHT / 2 - 120, WIDTH, HEIGHT / 2 - 116,
            fill=color, outline="", tags="dyn"
        )
        self.canvas.create_rectangle(
            0, HEIGHT / 2 + 116, WIDTH, HEIGHT / 2 + 120,
            fill=color, outline="", tags="dyn"
        )
        self.canvas.create_text(
            WIDTH / 2, HEIGHT / 2 - 30, text=title,
            fill=color, font=("Consolas", 40, "bold"), tags="dyn"
        )
        self.canvas.create_text(
            WIDTH / 2, HEIGHT / 2 + 40, text=subtitle, justify="center",
            fill="#e0e0e0", font=("Consolas", 15), tags="dyn"
        )

    def _hint(self, text):
        self.canvas.create_text(
            WIDTH / 2, HEIGHT - 30, text=text,
            fill="#e0e0e0", font=("Consolas", 14), tags="dyn"
        )


def main():
    root = tk.Tk()
    BreakoutGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
