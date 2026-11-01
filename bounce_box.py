"""
Bounce Box - a tiny, Scratch-style arcade game.

Keep the ball bouncing inside the box with your paddle.
Every paddle hit scores points, combos raise your multiplier,
grab the stars for bonus points, and get your name on the leaderboard!

Controls: Mouse or Left/Right (A/D) to move, P/Esc to pause.
"""
import json
import math
import os
import random
import sys
from array import array

import pygame

# ----------------------------------------------------------------- settings
WIDTH, HEIGHT = 800, 600
FPS = 60
TITLE = "Bounce Box"

HUD_H = 70
ARENA = pygame.Rect(30, HUD_H + 10, WIDTH - 60, HEIGHT - HUD_H - 30)
WALL = 8

LIVES = 3
MAX_NAME = 10
LEADERBOARD_SIZE = 10

# Scratch-ish bright palette
BG_TOP = (36, 32, 86)
BG_BOT = (18, 70, 120)
WHITE = (255, 255, 255)
INK = (30, 30, 50)
SOFT = (200, 210, 240)
YELLOW = (255, 204, 51)
ORANGE = (255, 140, 26)
PINK = (255, 102, 170)
CYAN = (76, 201, 240)
GREEN = (89, 203, 94)
PURPLE = (153, 102, 255)
RED = (255, 85, 85)
WALL_COL = (76, 151, 255)


# ----------------------------------------------------------------- helpers
def data_dir():
    """Writable folder for the leaderboard (works for a frozen .exe too)."""
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "BounceBox")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        path = os.path.abspath(".")
    return path


LEADERBOARD_FILE = os.path.join(data_dir(), "leaderboard.json")


def load_leaderboard():
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        board = [
            {"name": str(e["name"])[:MAX_NAME], "score": int(e["score"])}
            for e in data
            if isinstance(e, dict) and "name" in e and "score" in e
        ]
    except (OSError, ValueError, TypeError, KeyError):
        board = []
    board.sort(key=lambda e: e["score"], reverse=True)
    return board[:LEADERBOARD_SIZE]


def save_leaderboard(board):
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(board[:LEADERBOARD_SIZE], f, indent=2)
    except OSError:
        pass


def qualifies(board, score):
    if score <= 0:
        return False
    return len(board) < LEADERBOARD_SIZE or score > board[-1]["score"]


def make_tone(freq, ms, volume=0.35, kind="square", slide=0.0):
    """Generate a short retro sound effect without any external files."""
    rate = 22050
    n = int(rate * ms / 1000)
    buf = array("h")
    phase = 0.0
    for i in range(n):
        t = i / n
        f = freq * (1 + slide * t)
        phase += f / rate
        if kind == "square":
            v = 1.0 if (phase % 1.0) < 0.5 else -1.0
        else:
            v = math.sin(phase * 2 * math.pi)
        env = min(1.0, i / 80) * (1 - t) ** 2
        buf.append(int(v * env * volume * 32767))
    return pygame.mixer.Sound(buffer=buf.tobytes())


class Sounds:
    def __init__(self):
        self.ok = pygame.mixer.get_init() is not None
        if not self.ok:
            return
        try:
            self.paddle = make_tone(520, 90, slide=0.4)
            self.wall = make_tone(300, 50, 0.2, "sine")
            self.star = make_tone(880, 220, 0.3, "sine", slide=0.8)
            self.lose = make_tone(220, 450, 0.35, slide=-0.6)
            self.click = make_tone(660, 40, 0.2, "sine")
            self.level = make_tone(700, 300, 0.3, slide=1.0)
        except Exception:
            self.ok = False

    def play(self, name):
        if self.ok:
            getattr(self, name).play()


def vertical_gradient(size, top, bottom):
    surf = pygame.Surface(size)
    w, h = size
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.line(surf, c, (0, y), (w, y))
    return surf


def draw_text(surf, text, font, color, center=None, topleft=None, shadow=True):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        sh.set_alpha(110)
        surf.blit(sh, rect.move(3, 3))
    surf.blit(img, rect)
    return rect


def draw_star(surf, color, center, r, angle=0.0):
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.45
        a = angle + i * math.pi / 5 - math.pi / 2
        pts.append((center[0] + math.cos(a) * rad, center[1] + math.sin(a) * rad))
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, WHITE, pts, 2)


def draw_heart(surf, color, center, s):
    x, y = center
    pygame.draw.circle(surf, color, (x - s // 2, y - s // 4), s // 2)
    pygame.draw.circle(surf, color, (x + s // 2, y - s // 4), s // 2)
    pygame.draw.polygon(surf, color, [(x - s, y - s // 6), (x + s, y - s // 6), (x, y + s)])


# ----------------------------------------------------------------- entities
class Particle:
    def __init__(self, x, y, color):
        a = random.uniform(0, math.tau)
        sp = random.uniform(1.5, 6)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp
        self.life = random.randint(20, 40)
        self.max_life = self.life
        self.color = color
        self.size = random.randint(3, 6)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15
        self.vx *= 0.97
        self.life -= 1

    def draw(self, surf):
        r = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)


class Popup:
    def __init__(self, x, y, text, color, font):
        self.x, self.y = x, y
        self.img = font.render(text, True, color)
        self.life = 50

    def update(self):
        self.y -= 1.2
        self.life -= 1

    def draw(self, surf):
        self.img.set_alpha(max(0, min(255, self.life * 8)))
        surf.blit(self.img, self.img.get_rect(center=(int(self.x), int(self.y))))


class Paddle:
    W, H = 120, 18

    def __init__(self):
        self.rect = pygame.Rect(0, 0, self.W, self.H)
        self.rect.midbottom = (ARENA.centerx, ARENA.bottom - 18)
        self.x = float(self.rect.x)
        self.squash = 0.0

    def update(self, keys, mouse_x, use_mouse):
        speed = 9
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.x -= speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.x += speed
        if use_mouse:
            self.x += (mouse_x - self.W / 2 - self.x) * 0.35
        lo, hi = ARENA.left + WALL, ARENA.right - WALL - self.W
        self.x = max(lo, min(hi, self.x))
        self.rect.x = int(self.x)
        self.squash *= 0.85

    def draw(self, surf):
        r = self.rect.inflate(int(self.squash * 16), -int(self.squash * 6))
        r.centery = self.rect.centery + int(self.squash * 3)
        shadow = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 90), shadow.get_rect(), border_radius=9)
        surf.blit(shadow, r.move(0, 5))
        pygame.draw.rect(surf, ORANGE, r, border_radius=9)
        top = r.copy()
        top.height = r.height // 2
        pygame.draw.rect(surf, YELLOW, top, border_radius=9)
        pygame.draw.rect(surf, WHITE, r, 2, border_radius=9)


class Ball:
    R = 12

    def __init__(self, speed):
        self.x = float(ARENA.centerx)
        self.y = float(ARENA.top + 120)
        ang = random.uniform(-0.6, 0.6)
        self.speed = speed
        self.vx = math.sin(ang) * speed
        self.vy = math.cos(ang) * speed
        self.trail = []
        self.spin = 0.0

    @property
    def pos(self):
        return int(self.x), int(self.y)

    def set_speed(self, s):
        cur = math.hypot(self.vx, self.vy) or 1
        self.vx *= s / cur
        self.vy *= s / cur
        self.speed = s

    def draw(self, surf):
        for i, (tx, ty) in enumerate(self.trail):
            a = (i + 1) / len(self.trail)
            r = int(self.R * a * 0.9)
            s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*PINK, int(110 * a)), (r + 1, r + 1), r)
            surf.blit(s, (tx - r - 1, ty - r - 1))
        pygame.draw.circle(surf, PINK, self.pos, self.R)
        pygame.draw.circle(surf, WHITE, self.pos, self.R, 2)
        hx = self.x - 4 + math.cos(self.spin) * 1.5
        hy = self.y - 4 + math.sin(self.spin) * 1.5
        pygame.draw.circle(surf, (255, 200, 225), (int(hx), int(hy)), 4)


class Star:
    def __init__(self):
        margin = 50
        self.x = random.randint(ARENA.left + margin, ARENA.right - margin)
        self.y = random.randint(ARENA.top + margin, ARENA.bottom - 160)
        self.t = 0.0
        self.life = FPS * 8

    def update(self):
        self.t += 0.05
        self.life -= 1

    def draw(self, surf):
        bob = math.sin(self.t * 2) * 4
        r = 16 + math.sin(self.t * 4) * 2
        if self.life < FPS * 2 and (self.life // 6) % 2 == 0:
            return
        glow = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*YELLOW, 60), (40, 40), 30)
        surf.blit(glow, (self.x - 40, self.y - 40 + bob))
        draw_star(surf, YELLOW, (self.x, self.y + bob), r, self.t)


class Button:
    def __init__(self, text, center, color, w=260, h=60):
        self.text = text
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = center
        self.color = color
        self.hover = False

    def draw(self, surf, font):
        r = self.rect.copy()
        if self.hover:
            r = r.inflate(10, 6)
        pygame.draw.rect(surf, (0, 0, 0), r.move(0, 6), border_radius=16)
        pygame.draw.rect(surf, self.color, r, border_radius=16)
        hl = r.copy()
        hl.height //= 2
        lighter = tuple(min(255, c + 40) for c in self.color)
        pygame.draw.rect(surf, lighter, hl, border_radius=16)
        pygame.draw.rect(surf, WHITE, r, 3, border_radius=16)
        draw_text(surf, self.text, font, WHITE, center=r.center)


# ----------------------------------------------------------------- game
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.f_huge = pygame.font.Font(None, 96)
        self.f_big = pygame.font.Font(None, 64)
        self.f_med = pygame.font.Font(None, 42)
        self.f_small = pygame.font.Font(None, 30)
        self.f_tiny = pygame.font.Font(None, 24)
        self.bg = vertical_gradient((WIDTH, HEIGHT), BG_TOP, BG_BOT)
        self.sounds = Sounds()
        self.board = load_leaderboard()
        self.bg_dots = [
            (random.randint(0, WIDTH), random.randint(0, HEIGHT), random.uniform(0.2, 1.0))
            for _ in range(60)
        ]
        self.tick = 0
        self.state = "menu"
        self.menu_buttons = [
            Button("PLAY", (WIDTH // 2, 330), GREEN),
            Button("LEADERBOARD", (WIDTH // 2, 410), PURPLE),
            Button("QUIT", (WIDTH // 2, 490), RED),
        ]
        self.back_button = Button("BACK", (WIDTH // 2, HEIGHT - 55), ORANGE, 200, 54)
        self.demo_ball = Ball(5)
        self.use_mouse = True
        self.highlight = -1
        self.reset()

    # -- state -------------------------------------------------------------
    def reset(self):
        self.paddle = Paddle()
        self.ball = Ball(6.0)
        self.score = 0
        self.lives = LIVES
        self.hits = 0
        self.combo = 0
        self.level = 1
        self.particles = []
        self.popups = []
        self.star = None
        self.star_timer = FPS * 4
        self.shake = 0
        self.serve_timer = FPS
        self.name = ""
        self.flash = 0

    @property
    def multiplier(self):
        return min(5, 1 + self.combo // 5)

    def burst(self, x, y, color, n=16):
        for _ in range(n):
            self.particles.append(Particle(x, y, color))

    def popup(self, x, y, text, color):
        self.popups.append(Popup(x, y, text, color, self.f_med))

    # -- update ------------------------------------------------------------
    def update_play(self):
        keys = pygame.key.get_pressed()
        mx, _ = pygame.mouse.get_pos()
        self.paddle.update(keys, mx, self.use_mouse)

        if self.serve_timer > 0:
            self.serve_timer -= 1
            self.ball.x = self.paddle.rect.centerx
            self.ball.y = self.paddle.rect.top - Ball.R - 2
            if self.serve_timer == 0:
                ang = random.uniform(-0.5, 0.5)
                self.ball.vx = math.sin(ang) * self.ball.speed
                self.ball.vy = -math.cos(ang) * self.ball.speed
            return

        b = self.ball
        b.trail.append(b.pos)
        b.trail = b.trail[-10:]
        b.spin += 0.3
        # Sub-steps keep fast balls from tunnelling through things
        steps = max(1, int(b.speed // 6) + 1)
        for _ in range(steps):
            b.x += b.vx / steps
            b.y += b.vy / steps
            self.collide_walls(b)
            if self.collide_paddle(b):
                break

        if self.star:
            self.star.update()
            if math.hypot(b.x - self.star.x, b.y - self.star.y) < Ball.R + 18:
                bonus = 50 * self.multiplier
                self.score += bonus
                self.burst(self.star.x, self.star.y, YELLOW, 30)
                self.popup(self.star.x, self.star.y - 20, f"+{bonus}", YELLOW)
                self.sounds.play("star")
                self.star = None
                self.star_timer = random.randint(FPS * 4, FPS * 8)
            elif self.star.life <= 0:
                self.star = None
                self.star_timer = random.randint(FPS * 3, FPS * 6)
        else:
            self.star_timer -= 1
            if self.star_timer <= 0:
                self.star = Star()

        if b.y - Ball.R > ARENA.bottom:
            self.lose_life()

    def collide_walls(self, b):
        left, right = ARENA.left + WALL + Ball.R, ARENA.right - WALL - Ball.R
        top = ARENA.top + WALL + Ball.R
        hit = False
        if b.x < left:
            b.x, b.vx, hit = left, abs(b.vx), True
        elif b.x > right:
            b.x, b.vx, hit = right, -abs(b.vx), True
        if b.y < top:
            b.y, b.vy, hit = top, abs(b.vy), True
        if hit:
            self.sounds.play("wall")
            self.burst(b.x, b.y, CYAN, 6)

    def collide_paddle(self, b):
        p = self.paddle.rect
        if b.vy <= 0:
            return False
        if p.left - Ball.R < b.x < p.right + Ball.R and p.top - Ball.R < b.y < p.top + 8:
            # Angle depends on where the ball hits the paddle
            offset = (b.x - p.centerx) / (p.width / 2)
            offset = max(-1, min(1, offset))
            ang = offset * 1.05
            self.hits += 1
            self.combo += 1
            new_speed = min(16, 6 + self.hits * 0.25)
            b.vx = math.sin(ang) * new_speed
            b.vy = -abs(math.cos(ang) * new_speed)
            b.speed = new_speed
            b.y = p.top - Ball.R
            pts = 10 * self.multiplier
            self.score += pts
            self.popup(b.x, p.top - 30, f"+{pts}", YELLOW if self.multiplier > 1 else WHITE)
            self.burst(b.x, p.top, ORANGE, 14)
            self.paddle.squash = 1.0
            self.shake = 4
            self.sounds.play("paddle")
            new_level = 1 + self.hits // 10
            if new_level > self.level:
                self.level = new_level
                self.flash = 30
                self.sounds.play("level")
                self.popup(WIDTH // 2, ARENA.centery, f"LEVEL {self.level}!", GREEN)
            return True
        return False

    def lose_life(self):
        self.lives -= 1
        self.combo = 0
        self.shake = 16
        self.burst(self.ball.x, ARENA.bottom, RED, 40)
        self.sounds.play("lose")
        if self.lives <= 0:
            self.board = load_leaderboard()
            self.state = "enter_name" if qualifies(self.board, self.score) else "gameover"
        else:
            keep = self.ball.speed
            self.ball = Ball(max(6.0, keep - 2))
            self.serve_timer = FPS

    def submit_name(self):
        name = self.name.strip() or "PLAYER"
        self.board.append({"name": name, "score": self.score})
        self.board.sort(key=lambda e: e["score"], reverse=True)
        self.board = self.board[:LEADERBOARD_SIZE]
        save_leaderboard(self.board)
        self.highlight = next(
            (i for i, e in enumerate(self.board) if e["name"] == name and e["score"] == self.score),
            -1,
        )
        self.state = "leaderboard"

    def update_fx(self):
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.popups:
            p.update()
        self.popups = [p for p in self.popups if p.life > 0]
        if self.shake > 0:
            self.shake -= 1
        if self.flash > 0:
            self.flash -= 1

    def update_demo(self):
        b = self.demo_ball
        b.trail.append(b.pos)
        b.trail = b.trail[-10:]
        b.x += b.vx
        b.y += b.vy
        if b.x < Ball.R or b.x > WIDTH - Ball.R:
            b.vx *= -1
        if b.y < Ball.R or b.y > HEIGHT - Ball.R:
            b.vy *= -1
        b.x = max(Ball.R, min(WIDTH - Ball.R, b.x))
        b.y = max(Ball.R, min(HEIGHT - Ball.R, b.y))

    # -- drawing -----------------------------------------------------------
    def draw_background(self, s):
        s.blit(self.bg, (0, 0))
        for x, y, z in self.bg_dots:
            yy = (y + self.tick * z * 0.3) % HEIGHT
            c = int(90 + 120 * z)
            s.set_at((x, int(yy)), (c, c, min(255, c + 30)))

    def draw_arena(self, s):
        inner = pygame.Surface(ARENA.size, pygame.SRCALPHA)
        pygame.draw.rect(inner, (10, 15, 40, 120), inner.get_rect(), border_radius=18)
        for gx in range(0, ARENA.width, 40):
            pygame.draw.line(inner, (255, 255, 255, 14), (gx, 0), (gx, ARENA.height))
        for gy in range(0, ARENA.height, 40):
            pygame.draw.line(inner, (255, 255, 255, 14), (0, gy), (ARENA.width, gy))
        s.blit(inner, ARENA.topleft)
        col = GREEN if self.flash and (self.flash // 4) % 2 == 0 else WALL_COL
        # Walls on left, top and right - the bottom is open!
        pygame.draw.rect(s, col, ARENA, WALL, border_radius=18)
        danger = pygame.Rect(ARENA.left + 14, ARENA.bottom - WALL, ARENA.width - 28, WALL + 2)
        pygame.draw.rect(s, (40, 30, 80), danger)
        for x in range(danger.left, danger.right, 24):
            pygame.draw.line(s, RED, (x, danger.bottom), (x + 12, danger.top), 3)

    def draw_hud(self, s):
        bar = pygame.Rect(16, 10, WIDTH - 32, HUD_H - 14)
        pygame.draw.rect(s, (0, 0, 0), bar.move(0, 4), border_radius=14)
        pygame.draw.rect(s, (255, 255, 255), bar, border_radius=14)
        pygame.draw.rect(s, WALL_COL, bar, 3, border_radius=14)
        draw_text(s, "SCORE", self.f_tiny, (120, 120, 150), topleft=(34, 18), shadow=False)
        draw_text(s, str(self.score), self.f_big, INK, topleft=(34, 30), shadow=False)
        best = self.board[0]["score"] if self.board else 0
        draw_text(s, "BEST", self.f_tiny, (120, 120, 150), topleft=(220, 18), shadow=False)
        draw_text(s, str(max(best, self.score)), self.f_med, PURPLE, topleft=(220, 36), shadow=False)
        draw_text(s, "LEVEL", self.f_tiny, (120, 120, 150), topleft=(350, 18), shadow=False)
        draw_text(s, str(self.level), self.f_med, GREEN, topleft=(350, 36), shadow=False)
        if self.multiplier > 1:
            pill = pygame.Rect(430, 26, 90, 30)
            pygame.draw.rect(s, ORANGE, pill, border_radius=15)
            draw_text(s, f"x{self.multiplier}", self.f_small, WHITE, center=pill.center, shadow=False)
        for i in range(LIVES):
            col = RED if i < self.lives else (210, 210, 220)
            draw_heart(s, col, (WIDTH - 60 - i * 44, 40), 14)

    def draw_play(self, s):
        self.draw_background(s)
        self.draw_arena(s)
        if self.star:
            self.star.draw(s)
        self.paddle.draw(s)
        self.ball.draw(s)
        for p in self.particles:
            p.draw(s)
        for p in self.popups:
            p.draw(s)
        self.draw_hud(s)
        if self.serve_timer > 0 and self.state == "play":
            draw_text(s, "GET READY!", self.f_big, WHITE, center=(WIDTH // 2, ARENA.centery))

    def dim(self, s, alpha=150):
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((10, 10, 30, alpha))
        s.blit(ov, (0, 0))

    def panel(self, s, rect):
        pygame.draw.rect(s, (0, 0, 0), rect.move(0, 8), border_radius=24)
        pygame.draw.rect(s, WHITE, rect, border_radius=24)
        pygame.draw.rect(s, WALL_COL, rect, 4, border_radius=24)

    def draw_title(self, s, y):
        bob = math.sin(self.tick * 0.06) * 6
        colors = [PINK, ORANGE, YELLOW, GREEN, CYAN, PURPLE, PINK, ORANGE, YELLOW, GREEN]
        word = "BOUNCE BOX"
        imgs = [self.f_huge.render(ch, True, colors[i % len(colors)]) for i, ch in enumerate(word)]
        total = sum(i.get_width() for i in imgs) + 4 * len(imgs)
        x = WIDTH // 2 - total // 2
        for i, img in enumerate(imgs):
            off = math.sin(self.tick * 0.08 + i * 0.6) * 8 + bob
            sh = self.f_huge.render(word[i], True, (0, 0, 0))
            sh.set_alpha(120)
            s.blit(sh, (x + 4, y + off + 5))
            s.blit(img, (x, y + off))
            x += img.get_width() + 4

    def draw_menu(self, s):
        self.draw_background(s)
        self.demo_ball.draw(s)
        self.draw_title(s, 110)
        draw_text(s, "Keep the ball in the box. Rack up points!", self.f_small, SOFT,
                  center=(WIDTH // 2, 235))
        for b in self.menu_buttons:
            b.draw(s, self.f_med)
        draw_text(s, "Mouse or Arrow keys / A-D to move   -   P to pause", self.f_tiny, SOFT,
                  center=(WIDTH // 2, HEIGHT - 30))

    def draw_leaderboard(self, s):
        self.draw_background(s)
        rect = pygame.Rect(150, 30, 500, 470)
        self.panel(s, rect)
        draw_star(s, YELLOW, (rect.left + 36, rect.top + 50), 18, self.tick * 0.03)
        draw_star(s, YELLOW, (rect.right - 36, rect.top + 50), 18, -self.tick * 0.03)
        draw_text(s, "LEADERBOARD", self.f_big, PURPLE, center=(WIDTH // 2, rect.top + 50), shadow=False)
        if not self.board:
            draw_text(s, "No scores yet - go play!", self.f_med, (140, 140, 160),
                      center=(WIDTH // 2, rect.centery), shadow=False)
        medal = [YELLOW, (200, 200, 215), (215, 140, 70)]
        for i, e in enumerate(self.board):
            y = rect.top + 100 + i * 36
            row = pygame.Rect(rect.left + 24, y, rect.width - 48, 32)
            if i == self.highlight and (self.tick // 15) % 2 == 0:
                pygame.draw.rect(s, (255, 240, 180), row, border_radius=10)
            elif i % 2 == 0:
                pygame.draw.rect(s, (238, 242, 255), row, border_radius=10)
            badge_col = medal[i] if i < 3 else WALL_COL
            pygame.draw.circle(s, badge_col, (row.left + 22, row.centery), 13)
            draw_text(s, str(i + 1), self.f_tiny, WHITE if i >= 3 else INK,
                      center=(row.left + 22, row.centery + 1), shadow=False)
            draw_text(s, e["name"], self.f_small, INK, topleft=(row.left + 50, row.top + 6), shadow=False)
            img = self.f_small.render(str(e["score"]), True, ORANGE)
            s.blit(img, img.get_rect(midright=(row.right - 14, row.centery + 1)))
        self.back_button.draw(s, self.f_med)

    def draw_enter_name(self, s):
        self.draw_play(s)
        self.dim(s)
        rect = pygame.Rect(170, 140, 460, 320)
        self.panel(s, rect)
        draw_text(s, "NEW HIGH SCORE!", self.f_big, ORANGE, center=(WIDTH // 2, rect.top + 55), shadow=False)
        draw_text(s, str(self.score), self.f_huge, PURPLE, center=(WIDTH // 2, rect.top + 125), shadow=False)
        draw_text(s, "Type your name:", self.f_small, (110, 110, 140), center=(WIDTH // 2, rect.top + 180),
                  shadow=False)
        box = pygame.Rect(0, 0, 320, 54)
        box.center = (WIDTH // 2, rect.top + 230)
        pygame.draw.rect(s, (238, 242, 255), box, border_radius=12)
        pygame.draw.rect(s, WALL_COL, box, 3, border_radius=12)
        cursor = "_" if (self.tick // 20) % 2 == 0 else " "
        draw_text(s, self.name + cursor, self.f_med, INK, center=box.center, shadow=False)
        draw_text(s, "Press ENTER to save", self.f_tiny, (140, 140, 160), center=(WIDTH // 2, rect.bottom - 26),
                  shadow=False)

    def draw_gameover(self, s):
        self.draw_play(s)
        self.dim(s)
        rect = pygame.Rect(200, 150, 400, 300)
        self.panel(s, rect)
        draw_text(s, "GAME OVER", self.f_big, RED, center=(WIDTH // 2, rect.top + 60), shadow=False)
        draw_text(s, "Your score", self.f_small, (110, 110, 140), center=(WIDTH // 2, rect.top + 115), shadow=False)
        draw_text(s, str(self.score), self.f_huge, PURPLE, center=(WIDTH // 2, rect.top + 170), shadow=False)
        draw_text(s, "SPACE: play again    ESC: menu", self.f_tiny, (140, 140, 160),
                  center=(WIDTH // 2, rect.bottom - 35), shadow=False)

    def draw_pause(self, s):
        self.draw_play(s)
        self.dim(s, 120)
        draw_text(s, "PAUSED", self.f_huge, WHITE, center=(WIDTH // 2, HEIGHT // 2 - 20))
        draw_text(s, "P to resume  -  ESC for menu", self.f_small, SOFT, center=(WIDTH // 2, HEIGHT // 2 + 45))

    def render(self):
        s = self.canvas
        {
            "menu": self.draw_menu,
            "play": self.draw_play,
            "pause": self.draw_pause,
            "leaderboard": self.draw_leaderboard,
            "enter_name": self.draw_enter_name,
            "gameover": self.draw_gameover,
        }[self.state](s)
        ox = oy = 0
        if self.shake:
            ox, oy = random.randint(-self.shake, self.shake), random.randint(-self.shake, self.shake)
        self.screen.fill((0, 0, 0))
        self.screen.blit(s, (ox, oy))
        pygame.display.flip()

    # -- events ------------------------------------------------------------
    def handle(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type == pygame.MOUSEMOTION:
            self.use_mouse = True
            for b in self.menu_buttons + [self.back_button]:
                b.hover = b.rect.collidepoint(e.pos)
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            self.use_mouse = False

        if self.state == "menu":
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for b in self.menu_buttons:
                    if b.rect.collidepoint(e.pos):
                        self.sounds.play("click")
                        if b.text == "PLAY":
                            self.reset()
                            self.state = "play"
                        elif b.text == "LEADERBOARD":
                            self.board = load_leaderboard()
                            self.highlight = -1
                            self.state = "leaderboard"
                        else:
                            return False
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.reset()
                    self.state = "play"
                elif e.key == pygame.K_l:
                    self.state = "leaderboard"
                elif e.key == pygame.K_ESCAPE:
                    return False

        elif self.state == "play":
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_p, pygame.K_ESCAPE):
                self.state = "pause"

        elif self.state == "pause":
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_p:
                    self.state = "play"
                elif e.key == pygame.K_ESCAPE:
                    self.state = "menu"

        elif self.state == "leaderboard":
            back = e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.back_button.rect.collidepoint(e.pos)
            if back or (e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE)):
                self.sounds.play("click")
                self.state = "menu"

        elif self.state == "enter_name":
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_RETURN:
                    self.sounds.play("click")
                    self.submit_name()
                elif e.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                elif e.unicode and e.unicode.isprintable() and len(self.name) < MAX_NAME:
                    self.name += e.unicode.upper()

        elif self.state == "gameover":
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_SPACE:
                    self.reset()
                    self.state = "play"
                elif e.key == pygame.K_ESCAPE:
                    self.state = "menu"
            if e.type == pygame.MOUSEBUTTONDOWN:
                self.state = "menu"
        return True

    def step(self):
        self.tick += 1
        if self.state == "play":
            self.update_play()
        if self.state in ("menu", "leaderboard"):
            self.update_demo()
        self.update_fx()

    def run(self):
        running = True
        while running:
            for e in pygame.event.get():
                if not self.handle(e):
                    running = False
            self.step()
            self.render()
            self.clock.tick(FPS)


def main():
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init(22050, -16, 1, 512)
        except pygame.error:
            pass
    pygame.display.set_caption(TITLE)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(icon, PINK, (16, 16), 14)
    pygame.draw.circle(icon, WHITE, (16, 16), 14, 2)
    pygame.display.set_icon(icon)
    Game(screen).run()
    pygame.quit()


if __name__ == "__main__":
    main()
    sys.exit(0)
